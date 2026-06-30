"""Editör LLM aşaması — aday havuz + dağıtım + haftalık özet (Faz 6.5).

ADR-0003 / `Docs/04` §9.2 Aşama 0–1:

- **Aşama 0 (aday havuz):** `news.processed_items` üzerinde
  `relevance_score*100 >= min_content_score` + tarih aralığı; `relevance_score
  DESC`. Bülten-bazında kategori ön-filtresi yok (`Docs/04` §8.4).
- **Aşama 1 (editör LLM):** `summary_system_prompt` + `summary_user_prompt`
  render edilir, LLM çağrılır ve çıktı
  `{summary, assignments:[{section, article_ids}], dropped}` parse edilir.

Prompt değişkenleri tek-süslü `{degisken}` biçimindedir
(`Docs/03` §5 + `fixtures/newsletter_templates.json`); bu yüzden Jinja yerine
güvenli hedefli ikame (`render_prompt`) kullanılır — makale içeriğindeki serbest
`{`/`}` karakterleri bozulmaz.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any, Protocol

from packages.shared.enums import LlmRequestType
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_engine.digest_models import (
    DigestArticle,
    DigestTypeQueryConfig,
    EditorResult,
    SectionAssignment,
)
from services.ai_engine.exceptions import DigestParseError
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.processed_item_repository import (
    ProcessedItemRepository,
    processed_item_repository,
)

logger = logging.getLogger("ygip.ai_engine.editor_selector")

_NEWS_SCHEMA = "news"

# Editör aşaması bir triyaj/dağıtım adımıdır: LLM her adayın TAM metnine değil,
# alaka ve bölüm kararını verebilecek kısa bir parçasına ihtiyaç duyar. Bu yüzden
# her aday kısa bir snippet'e indirgenir ve toplam bütçe tüm aday havuzu (≈100
# haber) tek prompt'a sığacak şekilde yükseltilir. Aksi halde tek bir uzun haber
# bütçeyi tüketip diğer adayların editöre hiç ulaşmamasına yol açar.
# ~100 haber × ~1000 krk ≈ 130k krk ≈ ~32k token (groq 128k context içinde).
_EDITOR_PER_ARTICLE_CHARS = 1000
_EDITOR_MAX_CHARS = 130000

# Editör ÇIKTISI ~100 adayın UUID'lerini (assignments + dropped) geri yazmak zorunda.
# UUID'ler token-yoğun olduğundan varsayılan 4096 çıktı bütçesi büyük aday havuzunda
# JSON'u ortadan kesip parse hatasına yol açıyordu — bu da dağıtımın tümüyle ilk
# bölüme düşmesine (parse hatası → DigestParseError) neden oluyordu. Geniş çıktı
# bütçesi bu kesilmeyi önler.
_EDITOR_MAX_OUTPUT_TOKENS = 8192

# Aday havuz tavanı — tüm bültenler için en az 100 haber editöre ulaşabilsin
# (skor sırasına göre ilk N). Yeterli aday yoksa havuzdaki kadarı gönderilir.
_DEFAULT_CANDIDATE_LIMIT = 100
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


class SectionLike(Protocol):
    """`editor_selector`'ın bölümden ihtiyaç duyduğu minimum arayüz."""

    name: str
    sort_order: int


class NewsletterLike(Protocol):
    """`editor_selector`'ın bültenden ihtiyaç duyduğu minimum arayüz."""

    name: str
    description: str
    summary_system_prompt: str
    summary_user_prompt: str
    min_content_score: int

    # Salt-okunur property (kovaryant) — ORM `Mapped[list[str]]` ile uyumlu;
    # `GeneratableNewsletter.content_categories` ile aynı imza.
    @property
    def content_categories(self) -> Sequence[str]: ...

    @property
    def sections(self) -> Sequence[SectionLike]: ...


class EditorSelector:
    """Aday havuz seçimi + editör LLM dağıtım/özet aşaması."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        processed_items: ProcessedItemRepository | None = None,
        candidate_limit: int = _DEFAULT_CANDIDATE_LIMIT,
    ) -> None:
        self._llm_client = llm_client
        self._processed_items = processed_items or processed_item_repository
        self._candidate_limit = candidate_limit

    async def select_candidates(
        self,
        db: AsyncSession,
        *,
        newsletter: NewsletterLike,
        period_start: date,
        period_end: date,
    ) -> list[DigestArticle]:
        """Aday havuzu — skor + tarih + (varsa) bülten içerik kategorisi filtresi."""
        config = DigestTypeQueryConfig(
            schema=_NEWS_SCHEMA,
            content_categories=tuple(newsletter.content_categories or ()),
        )
        min_relevance_score = max(0.0, min(newsletter.min_content_score / 100, 1.0))
        return await self._processed_items.list_for_digest(
            db,
            config=config,
            period_start=period_start,
            period_end=period_end,
            min_relevance_score=min_relevance_score,
            limit=self._candidate_limit,
        )

    async def run_editor(
        self,
        *,
        newsletter: NewsletterLike,
        articles: list[DigestArticle],
        period_start: date,
        period_end: date,
    ) -> EditorResult:
        """Editör LLM'i çalıştırır — dağıtım + haftalık özet."""
        context = {
            "newsletter_name": newsletter.name,
            "newsletter_description": newsletter.description,
            "date_range": f"{period_start.isoformat()} — {period_end.isoformat()}",
            "sections": format_section_names(newsletter.sections),
            "articles": format_articles_for_prompt(
                articles,
                max_chars=_EDITOR_MAX_CHARS,
                per_article_chars=_EDITOR_PER_ARTICLE_CHARS,
            ),
        }
        included = count_articles_in_prompt(context["articles"])
        if included < len(articles):
            logger.warning(
                "editor_prompt_truncated_candidates",
                extra={"selected": len(articles), "included_in_prompt": included},
            )
        system_prompt = render_prompt(newsletter.summary_system_prompt, context)
        user_prompt = render_prompt(newsletter.summary_user_prompt, context)

        response = await self._llm_client.complete(
            user_prompt,
            system_prompt=system_prompt,
            max_tokens=_EDITOR_MAX_OUTPUT_TOKENS,
            operation_type=LlmRequestType.DIGEST_GENERATION,
        )
        if response.usage.completion_tokens >= _EDITOR_MAX_OUTPUT_TOKENS:
            logger.warning(
                "editor_response_output_truncated",
                extra={
                    "completion_tokens": response.usage.completion_tokens,
                    "max_tokens": _EDITOR_MAX_OUTPUT_TOKENS,
                    "candidates": len(articles),
                },
            )
        return parse_editor_response(
            response.text,
            sections=newsletter.sections,
            articles=articles,
        )


def render_prompt(template: str, variables: dict[str, str]) -> str:
    """Tek-süslü `{degisken}` token'larını güvenli hedefli ikameyle doldurur."""
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered.strip()


def format_section_names(sections: Sequence[SectionLike]) -> str:
    """Editör prompt'u için `{sections}` — `sort_order: ad` satırları."""
    return "\n".join(f"{section.sort_order}: {section.name}" for section in sections)


def format_articles_for_prompt(
    articles: Sequence[DigestArticle],
    *,
    max_chars: int = 12000,
    per_article_chars: int | None = None,
) -> str:
    """Aday havuzu prompt context metnine dönüştürür (id + başlık + skor + içerik).

    `per_article_chars` verilirse her haberin içeriği bu uzunlukta bir snippet'e
    indirgenir — editör triyaj aşaması tam metne ihtiyaç duymaz, böylece tek bir
    uzun haber `max_chars` bütçesini tüketip diğer adayları prompt'tan dışlamaz.
    """
    if not articles:
        return ""

    blocks: list[str] = []
    used = 0
    for index, article in enumerate(articles, start=1):
        header = f"### Makale {index}: {article.title}"
        meta_lines = [
            f"ID: {article.processed_item_id}",
            f"Skor: {article.relevance_score:.2f}",
        ]
        if article.url:
            meta_lines.append(f"URL: {article.url}")
        if article.published_at is not None:
            meta_lines.append(f"Tarih: {article.published_at.date().isoformat()}")
        body = article.clean_content.strip()
        if per_article_chars is not None and len(body) > per_article_chars:
            body = body[:per_article_chars].rstrip() + " […]"
        block = "\n".join([header, *meta_lines, body, ""])
        if used + len(block) > max_chars and blocks:
            break
        blocks.append(block)
        used += len(block)
    return "\n".join(blocks).strip()


def count_articles_in_prompt(rendered_articles: str) -> int:
    """Prompt'a fiilen kaç haber bloğunun girdiğini sayar (`### Makale N:` başlığı)."""
    return len(re.findall(r"^### Makale \d+:", rendered_articles, flags=re.MULTILINE))


def parse_editor_response(
    raw_text: str,
    *,
    sections: Sequence[SectionLike],
    articles: Sequence[DigestArticle],
) -> EditorResult:
    """Editör JSON çıktısını parse eder; parse edilemezse `DigestParseError`.

    Halüsinasyon koruması: yalnızca aday havuzdaki `processed_item_id`'ler
    eşleştirilir; bilinmeyen id'ler atılır. Editörün `dropped` olarak işaretlediği
    haberler hiçbir bölüme atanmaz.

    Geçmişte bozuk JSON'da tüm haberler sessizce ilk bölüme atanıyordu; bu
    "hepsi tek bölümde" görünen yanlış bültenlere yol açtığından artık üretim
    açıkça başarısız olur (admin yeniden tetikler).
    """
    valid_ids = {article.processed_item_id for article in articles}
    payload = _extract_json_object(raw_text)
    if payload is None:
        logger.error(
            "editor_response_unparseable",
            extra={
                "candidates": len(articles),
                "raw_len": len(raw_text),
                "raw_preview": raw_text[:1500],
                **_describe_json_error(raw_text),
            },
        )
        raise DigestParseError(
            "Editör LLM çıktısı geçerli JSON değil; bülten bölüm dağıtımı yapılamadı.",
        )

    summary = _coerce_str(payload.get("summary"))
    dropped = _parse_id_list(payload.get("dropped"), valid_ids)
    assignments = _parse_assignments(
        payload.get("assignments"),
        sections=sections,
        valid_ids=valid_ids,
        dropped_set=set(dropped),
    )
    return EditorResult(summary=summary, assignments=assignments, dropped=dropped)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None

    candidates: list[str] = []
    block = _JSON_BLOCK_RE.search(stripped)
    if block:
        candidates.append(block.group(1))
    # String-duyarlı denge taraması: ilk dengeli {..} nesnesi (kod bloğu/önsöz/sonsöz
    # ne olursa olsun) — naif `rfind("}")` ile takip eden serbest metindeki `}`'lerin
    # nesneyi bozmasını engeller.
    balanced = _balanced_json_object(stripped)
    if balanced:
        candidates.append(balanced)
    candidates.append(stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])

    for candidate in candidates:
        parsed = _loads_tolerant(candidate)
        if isinstance(parsed, dict):
            return parsed
    return None


def _describe_json_error(raw_text: str) -> dict[str, Any]:
    """Parse edilemeyen çıktı için kesin JSON hatasını (sebep + konum + pencere) çıkarır.

    En iyi adayı (dengeli nesne, yoksa ham metin) `strict=False` ile parse etmeyi
    dener; `JSONDecodeError`'ın mesajını ve hatanın geçtiği konumun etrafındaki
    ~200 karakterlik pencereyi döner — log'da kök sebebi tek bakışta gösterir.
    """
    candidate = _balanced_json_object(raw_text) or raw_text.strip()
    try:
        json.loads(candidate, strict=False)
    except json.JSONDecodeError as exc:
        window = candidate[max(0, exc.pos - 100) : exc.pos + 100]
        return {
            "json_error": f"{exc.msg} (satır {exc.lineno}, sütun {exc.colno}, poz {exc.pos})",
            "error_window": window,
        }
    except (TypeError, ValueError):  # pragma: no cover - beklenmeyen tip
        return {}
    return {}


def _balanced_json_object(text: str) -> str | None:
    """İlk `{`'ten başlayıp string-içi tırnakları sayarak dengeli ilk nesneyi döner.

    String durumu izlenir (kaçışlı `\\"` dahil) — bu yüzden değer içindeki `{`/`}`
    derinliği bozmaz. Nesne kapanmadan metin biterse (truncation) `None` döner.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _loads_tolerant(candidate: str) -> Any:
    """`json.loads`; yaygın LLM-JSON kusurlarına toleranslı.

    İki kurtarma uygulanır:
    - **Trailing-comma temizliği**: uzun `article_ids`/`dropped` dizilerinde LLM'in
      bıraktığı sondaki virgül (`[..., ]`, `{..., }`) standart JSON'da hata verir.
    - **`strict=False`**: string değeri içinde kaçışsız yeni satır/tab gibi literal
      kontrol karakterlerine izin verir — uzun `summary` serbest metninde sık görülür
      ve tek başına editör çıktısını parse edilemez kılıp dağıtımı düşürebiliyordu.
    """
    for text in (candidate, _TRAILING_COMMA_RE.sub(r"\1", candidate)):
        for strict in (True, False):
            try:
                return json.loads(text, strict=strict)
            except json.JSONDecodeError:
                continue
    return None


def _parse_assignments(
    raw: Any,
    *,
    sections: Sequence[SectionLike],
    valid_ids: set[uuid.UUID],
    dropped_set: set[uuid.UUID],
) -> list[SectionAssignment]:
    if not isinstance(raw, list):
        return []

    by_section: dict[int, list[uuid.UUID]] = {}
    assigned: set[uuid.UUID] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        section = _match_section(item.get("section"), sections)
        if section is None:
            continue
        bucket = by_section.setdefault(section.sort_order, [])
        raw_ids = item.get("article_ids")
        if not isinstance(raw_ids, list):
            continue
        for raw_id in raw_ids:
            parsed = _coerce_uuid(raw_id)
            if (
                parsed is None
                or parsed not in valid_ids
                or parsed in dropped_set
                or parsed in assigned
            ):
                continue
            assigned.add(parsed)
            bucket.append(parsed)

    assignments: list[SectionAssignment] = []
    for section in sorted(sections, key=lambda item: item.sort_order):
        ids = by_section.get(section.sort_order)
        if not ids:
            continue
        assignments.append(
            SectionAssignment(
                section_name=section.name,
                sort_order=section.sort_order,
                article_ids=ids,
            )
        )
    return assignments


def _match_section(
    raw: Any,
    sections: Sequence[SectionLike],
) -> SectionLike | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, str):
        key = raw.strip().casefold()
        for section in sections:
            if section.name.casefold() == key:
                return section
        if key.isdigit():
            return _match_section_index(int(key), sections)
        # Editör prompt'ta bölümler "0: Ad" biçiminde listelendiğinden, LLM bazen
        # etiketin tamamını ("0: yıldız holding...") döndürür. Önekteki "N:" kısmını
        # ayırıp hem indeksle hem isimle eşleştirmeyi dener.
        prefix, sep, rest = key.partition(":")
        if sep and prefix.strip().isdigit():
            matched = _match_section_index(int(prefix.strip()), sections)
            if matched is not None:
                return matched
            rest_key = rest.strip()
            for section in sections:
                if section.name.casefold() == rest_key:
                    return section
        return None
    if isinstance(raw, int):
        return _match_section_index(raw, sections)
    return None


def _match_section_index(
    index: int,
    sections: Sequence[SectionLike],
) -> SectionLike | None:
    for section in sections:
        if section.sort_order == index:
            return section
    if 0 <= index < len(sections):
        return sections[index]
    return None


def _parse_id_list(raw: Any, valid_ids: set[uuid.UUID]) -> list[uuid.UUID]:
    result: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    if not isinstance(raw, list):
        return result
    for item in raw:
        parsed = _coerce_uuid(item)
        if parsed is None or parsed not in valid_ids or parsed in seen:
            continue
        seen.add(parsed)
        result.append(parsed)
    return result


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value).strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()

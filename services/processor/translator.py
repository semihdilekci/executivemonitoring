"""Translate processor — ingest-time EN→TR haber çevirisi (`Docs/04` §8.45, Faz 6.5).

Zincirdeki konum: `Scorer` (§8.4) sonrası, `Chunker` (§8.5) öncesi. Yalnızca
`language == "en"` **ve** `relevance_score*100 >= translation_min_relevance_score`
olan haberler tek `LLMClient.complete()` çağrısıyla Türkçeye çevrilir. Başarıda
canonical içerik (`title`/`clean_content`, `language="tr"`) güncellenir ve orijinal
İngilizce başlık+metin `extras["original_translation"]`'a konur (persist katmanı
`processed_item_translations`'a yazar). **Çeviri hatası haberi düşürmez:** hata/bozuk
çıktı durumunda içerik İngilizce haliyle geçirilir (no-op) ve olay loglanır.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from packages.shared.enums import LlmRequestType

from services.processor.base_processor import BaseProcessor
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.translator")

# İş/finans istihbaratı çevirisi için davranış sözleşmesi (`Docs/04` §8.45).
TRANSLATION_SYSTEM_PROMPT = (
    "Sen profesyonel bir iş ve finans istihbaratı çevirmenisin. Verilen İngilizce "
    "haberin başlığını ve metnini akıcı, profesyonel Türkçeye çevir. Kurallar:\n"
    "- Özel isimleri, kurum/şirket/marka adlarını ve sayısal değerleri (tutar, "
    "yüzde, tarih, oran) AYNEN koru.\n"
    "- ÖZETLEME, ekleme veya çıkarma yapma; metnin tamamını ve anlamını birebir "
    "aktar.\n"
    "- Finans-iş terminolojisini doğru ve yerleşik Türkçe karşılıklarıyla çevir.\n"
    "- Çıktıyı YALNIZCA şu JSON biçiminde ver, başka açıklama ekleme: "
    '{"title": "...", "content": "..."}'
)

# Çeviri tek istekte başlık+metni döndürür; uzun makaleler için cömert üst sınır.
_TRANSLATION_MAX_TOKENS = 8192

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL | re.IGNORECASE)


class TranslationProcessor(BaseProcessor):
    """`language=="en"` + eşik üstü haberleri TR'ye çeviren pipeline adımı.

    `llm_client` None ise (operasyon kapsamında aktif provider yok) adım no-op'tur.
    `process` hiçbir koşulda exception yükseltmez — çeviri hatası ingest'i kırmaz.
    """

    def __init__(
        self,
        *,
        llm_client: Any | None,
        min_relevance_score: int,
        max_tokens: int = _TRANSLATION_MAX_TOKENS,
    ) -> None:
        self._llm_client = llm_client
        self._min_relevance_score = min_relevance_score
        self._max_tokens = max_tokens

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        data = ctx.data

        if not self._should_translate(data):
            return data

        if self._llm_client is None:
            logger.info(
                "processor_translate_no_provider",
                extra={"source_id": str(data.source_id)},
            )
            return data

        source_title = data.title
        source_content = _source_content(data)
        try:
            response = await self._llm_client.complete(
                _build_user_prompt(source_title, source_content),
                system_prompt=TRANSLATION_SYSTEM_PROMPT,
                max_tokens=self._max_tokens,
                operation_type=LlmRequestType.ARTICLE_TRANSLATION,
            )
            parsed = parse_translation_response(response.text)
        except Exception as exc:  # noqa: BLE001 — çeviri hatası ingest'i kırmamalı
            logger.warning(
                "processor_translate_failed",
                extra={"source_id": str(data.source_id), "error": str(exc)},
            )
            return data

        if parsed is None:
            logger.warning(
                "processor_translate_unparseable",
                extra={"source_id": str(data.source_id)},
            )
            return data

        translated_title, translated_content = parsed
        data.title = translated_title
        data.content = translated_content
        data.extras["clean_content"] = translated_content
        data.extras["language"] = "tr"
        data.extras["original_translation"] = {
            "language": "en",
            "title": source_title,
            "content": source_content,
        }
        logger.info(
            "processor_translate_success",
            extra={"source_id": str(data.source_id)},
        )
        return data

    def _should_translate(self, data: ProcessorOutput) -> bool:
        language = data.extras.get("language")
        if language != "en":
            return False
        score_raw = data.extras.get("relevance_score", 0.0)
        score = float(score_raw) if isinstance(score_raw, (int, float)) else 0.0
        return score * 100 >= self._min_relevance_score


def _source_content(data: ProcessorOutput) -> str:
    """Çevrilecek metin — normalize edilmiş `clean_content`, yoksa ham içerik."""
    clean = data.extras.get("clean_content")
    return clean if isinstance(clean, str) and clean else data.content


def _build_user_prompt(title: str, content: str) -> str:
    return f"BAŞLIK:\n{title}\n\nMETİN:\n{content}"


def parse_translation_response(raw_text: str) -> tuple[str, str] | None:
    """Çeviri JSON çıktısını `(title, content)` olarak parse eder; bozuksa None.

    Hem başlık hem metin boş olmayan string olmalı; aksi halde çeviri geçersiz
    sayılır ve çağıran no-op'a düşer (`Docs/04` §8.45).
    """
    payload = _extract_json_object(raw_text)
    if payload is None:
        return None
    title = payload.get("title")
    content = payload.get("content")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    return title.strip(), content.strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None

    candidates: list[str] = []
    block = _JSON_BLOCK_RE.search(stripped)
    if block:
        candidates.append(block.group(1))
    candidates.append(stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None

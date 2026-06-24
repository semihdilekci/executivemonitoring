"""Keyword havuzu — gate ve enricher paylaşır (`Docs/04` §8.3–8.4).

Faz 6.3: hardcoded `CATEGORY_RULES` kaldırıldı. Aktif keyword havuzu artık
DB `keywords` + `keyword_category_ratings` tablolarından (`Docs/02` §4.20–4.21)
`KeywordPoolProvider` ile TTL-cache'li yüklenir. Her keyword `term_tr` + `term_en`
yüzeyine ve kategori-başına 1–10 rating'e sahiptir.

Bu modül DB'ye **bağımsızdır** (saf eşleşme + havuz mantığı); DB sorgusu
`services/processor/keyword_repository.py` tarafından yapılır ve `KeywordRecord`
listesi sağlanır.
"""

from __future__ import annotations

import asyncio
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import NamedTuple


class CategoryKeyword(NamedTuple):
    """Bir kategoriye ait keyword'ün çalışma-zamanı temsili (`Docs/04` §8.4)."""

    term_tr: str
    term_en: str
    rating: int


@dataclass(frozen=True)
class KeywordRecord:
    """DB'den yüklenen tek keyword — tr/en yüzey + kategori→rating haritası.

    `keyword_repository.load_active_keywords` üretir; `KeywordPoolProvider`
    bunları kategori havuzu + master havuza dönüştürür.
    """

    term_tr: str
    term_en: str
    ratings: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class KeywordPools:
    """Provider'ın ürettiği çalışma-zamanı havuzları."""

    category_pool: dict[str, list[CategoryKeyword]]
    master_pool: tuple[str, ...]


KeywordLoader = Callable[[], Awaitable[list[KeywordRecord]]]


def normalize_for_match(text: str) -> str:
    """Case-insensitive arama için NFC + lowercase."""
    return unicodedata.normalize("NFC", text).casefold()


@lru_cache(maxsize=512)
def _keyword_pattern(needle: str) -> re.Pattern[str]:
    """Keyword için kelime-sınırı (`\\b`) regex'i — substring yanlış-pozitiflerini önler.

    `ai` keyword'ü `hair`/`airport` içinde eşleşmez; `kur` `kurul` içinde eşleşmez.
    Çok kelimeli ifadeler (`merkez bankası`) için boşluk doğal sınırdır.
    """
    return re.compile(rf"\b{re.escape(needle)}\b")


def _keyword_in_haystack(haystack: str, keyword: str) -> bool:
    """Önceden normalize edilmiş haystack içinde keyword kelime-sınırı eşleşmesi."""
    return _keyword_pattern(normalize_for_match(keyword)).search(haystack) is not None


def count_total_keyword_hits(content: str, keywords: Iterable[str]) -> int:
    """Verilen keyword'lerin metindeki toplam (kelime-sınırlı) geçiş sayısı."""
    haystack = normalize_for_match(content)
    return sum(
        len(_keyword_pattern(normalize_for_match(keyword)).findall(haystack))
        for keyword in keywords
    )


def count_keyword_hits(content: str, keyword: CategoryKeyword) -> int:
    """Bir `CategoryKeyword`'ün (tr+en yüzey birleşik) metindeki geçiş sayısı.

    İki yüzey normalize sonrası aynıysa (çevirisiz marka/kurum) tek kez sayılır;
    aksi halde tr ve en yüzeyleri ayrı kelime-sınırı eşleşmesiyle toplanır.
    """
    haystack = normalize_for_match(content)
    surfaces = {
        normalized
        for normalized in (
            normalize_for_match(keyword.term_tr),
            normalize_for_match(keyword.term_en),
        )
        if normalized
    }
    return sum(len(_keyword_pattern(surface).findall(haystack)) for surface in surfaces)


def find_matching_keywords(
    title: str,
    content: str,
    keywords: Iterable[str],
) -> list[str]:
    """Title + body içinde eşleşen keyword yüzeylerini döner (case-insensitive, NFC).

    `keywords` çağıran tarafından sağlanır (master havuz veya kategori yüzeyleri).
    Çok kelimeli ifadelerin tek kelimeli olanlardan önce denenmesi için çağıran
    havuzu uzunluğa göre sıralamış olmalıdır (`KeywordPoolProvider.master_pool`).
    """
    haystack = normalize_for_match(f"{title} {content}")
    matched: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        needle = normalize_for_match(keyword)
        if needle not in seen and _keyword_in_haystack(haystack, keyword):
            seen.add(needle)
            matched.append(keyword)
    return matched


def has_master_match(title: str, content: str, master_pool: Iterable[str]) -> bool:
    """Master havuzda ≥1 eşleşme var mı? Gate kabul/DROP kararı bunu sorar."""
    haystack = normalize_for_match(f"{title} {content}")
    return any(_keyword_in_haystack(haystack, keyword) for keyword in master_pool)


def _keyword_record_matches(haystack: str, keyword: CategoryKeyword) -> bool:
    """Keyword'ün tr veya en yüzeyi metinde geçiyor mu?"""
    return _keyword_in_haystack(haystack, keyword.term_tr) or _keyword_in_haystack(
        haystack, keyword.term_en
    )


def count_matches_by_category(
    title: str,
    content: str,
    category_pool: dict[str, list[CategoryKeyword]],
) -> dict[str, list[CategoryKeyword]]:
    """Kategori başına eşleşen `CategoryKeyword` listesi (boş kategoriler atlanır)."""
    haystack = normalize_for_match(f"{title} {content}")
    result: dict[str, list[CategoryKeyword]] = {}
    for category, keywords in category_pool.items():
        matched = [kw for kw in keywords if _keyword_record_matches(haystack, kw)]
        if matched:
            result[category] = matched
    return result


def build_pools(records: Iterable[KeywordRecord]) -> KeywordPools:
    """`KeywordRecord` listesinden kategori havuzu + master havuz üretir.

    Master havuz tüm aktif keyword'lerin `term_tr` + `term_en` yüzeylerinin
    dedupe edilmiş birleşimidir; çok kelimeli ifadeler önce gelsin diye uzunluğa
    göre azalan sıralanır (`Docs/04` §8.4 — uzun-önce eşleşme).
    """
    category_pool: dict[str, list[CategoryKeyword]] = {}
    master_seen: set[str] = set()
    master: list[str] = []

    for record in records:
        for surface in (record.term_tr, record.term_en):
            normalized = normalize_for_match(surface)
            if normalized and normalized not in master_seen:
                master_seen.add(normalized)
                master.append(surface)
        for category, rating in record.ratings.items():
            category_pool.setdefault(category, []).append(
                CategoryKeyword(record.term_tr, record.term_en, rating)
            )

    master_sorted = tuple(sorted(master, key=len, reverse=True))
    return KeywordPools(category_pool=category_pool, master_pool=master_sorted)


class KeywordPoolProvider:
    """Aktif keyword havuzunu TTL-cache ile yükleyen sağlayıcı (`Docs/04` §8.3–8.4).

    `loader` her çağrıldığında DB'den (veya test sahtesinden) güncel
    `KeywordRecord` listesini döndürür. Provider bunu TTL süresince cache'ler;
    Lambda soğuk başlangıcında tek sorgu, sonraki çağrılarda cache hit (N+1 yok).
    """

    def __init__(
        self,
        loader: KeywordLoader,
        *,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._loader = loader
        self._ttl = ttl_seconds
        self._clock = clock
        self._cache: KeywordPools | None = None
        self._loaded_at: float | None = None
        self._lock = asyncio.Lock()

    def _is_fresh(self) -> bool:
        return (
            self._cache is not None
            and self._loaded_at is not None
            and (self._clock() - self._loaded_at) < self._ttl
        )

    async def get_pools(self) -> KeywordPools:
        """Cache taze ise onu, değilse DB'den yeniden yükleyip döner."""
        if self._is_fresh():
            assert self._cache is not None
            return self._cache
        async with self._lock:
            if self._is_fresh():
                assert self._cache is not None
                return self._cache
            records = await self._loader()
            self._cache = build_pools(records)
            self._loaded_at = self._clock()
            return self._cache

    async def master_pool(self) -> tuple[str, ...]:
        """Gate için tüm aktif keyword yüzeylerinin (tr+en) birleşimi."""
        return (await self.get_pools()).master_pool

    async def category_pool(self) -> dict[str, list[CategoryKeyword]]:
        """Enricher için kategori → rating taşıyan keyword listesi."""
        return (await self.get_pools()).category_pool

    def invalidate(self) -> None:
        """Cache'i boşaltır — sonraki `get_pools` yeniden yükler."""
        self._cache = None
        self._loaded_at = None


def static_keyword_pool_provider(records: Iterable[KeywordRecord]) -> KeywordPoolProvider:
    """Sabit `KeywordRecord` listesinden provider — test/dev için (DB yok)."""
    snapshot = list(records)

    async def _loader() -> list[KeywordRecord]:
        return list(snapshot)

    return KeywordPoolProvider(_loader)


# Faz 6.4 (ADR-0002): tüm haber içeriği `news.processed_items`'a yazılır.
# `content_category` (6 değer) ince sınıflandırmadır; PostgreSQL schema seçimini
# **belirlemez**. `market`/`fmcg`/`geo`/`transport` schema'ları MVP-1+ yapılandırılmış
# veri için rezerve — haber almazlar. Eski `content_category → schema` haritası
# (`CATEGORY_TO_SCHEMA`) bu fazda kaldırıldı.
ARTICLE_SCHEMA = "news"


def resolve_schema_category(category: str) -> str:
    """Haber depolama schema'sı — her zaman `news` (`Docs/04` §8.4, ADR-0002).

    `content_category`'den bağımsızdır. İmza geriye dönük uyum için korunur;
    argüman yok sayılır (eski kategori→schema routing kaldırıldı).
    """
    return ARTICLE_SCHEMA


def category_score(matched: list[CategoryKeyword]) -> int:
    """Bir kategoride eşleşen keyword'lerin rating toplamı (`Docs/04` §8.4 — K5).

    `count_matches_by_category` zaten distinct `CategoryKeyword` döndürdüğü için
    tekrar dedupe gerekmez; adet değil, rating toplamı kategori seçimini belirler.
    """
    return sum(keyword.rating for keyword in matched)


def resolve_content_category(
    title: str,
    content: str,
    *,
    ingest_mode: str,
    default_category: str,
    pools: KeywordPools,
) -> tuple[str, list[str], list[CategoryKeyword]]:
    """Kategori çözümleme — **rating-ağırlıklı** (`Docs/04` §8.4 — K5, Faz 6.3).

    Çözümleme sırası:
    1. `ingest_mode: "all"` → her zaman `default_category` (rating hesaplanmaz).
    2. `filtered` → her kategori için `category_score` (rating toplamı); **en
       yüksek toplam** kazanır.
    3. Eşitlik (≥2 kategori aynı en yüksek toplam) → `default_category`.
    4. Hiç kategori-keyword eşleşmesi yok → `default_category`.

    Döner: `(content_category, all_matched, scored)`.
    - `all_matched`: `topics` için tüm master eşleşmeleri (davranış değişmez).
    - `scored`: yalnızca **kazanan kategoriye** ait eşleşen keyword'ler (rating
      taşır); scorer bunu rating-ağırlıklı relevance için kullanır. Kazanan
      kategoride hiç eşleşme yoksa boş liste → skor `0.0`.
    """
    all_matched = find_matching_keywords(title, content, pools.master_pool)
    by_category = count_matches_by_category(title, content, pools.category_pool)

    def _scored_for(category: str) -> list[CategoryKeyword]:
        return by_category.get(category, [])

    if ingest_mode == "all":
        return default_category, all_matched, _scored_for(default_category)

    if not by_category:
        return default_category, all_matched, []

    scores = {category: category_score(matched) for category, matched in by_category.items()}
    max_score = max(scores.values())
    top_categories = [category for category, score in scores.items() if score == max_score]

    winner = top_categories[0] if len(top_categories) == 1 else default_category
    return winner, all_matched, _scored_for(winner)

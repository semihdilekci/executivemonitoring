"""Master keyword havuzu — gate ve enricher paylaşır (`Docs/04` §8.3–8.4)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from functools import lru_cache

CATEGORY_RULES: dict[str, dict[str, list[str]]] = {
    "macro": {
        "keywords": [
            "tcmb",
            "faiz",
            "enflasyon",
            "büyüme",
            "gsyih",
            "imf",
            "merkez bankası",
            "cari açık",
        ],
    },
    "fmcg": {
        "keywords": [
            "fmcg",
            "gıda",
            "perakende",
            "tüketici",
            "snack",
            "dairy",
            "bakery",
            "confectionery",
            "grocery",
            "cpg",
            "tüketim",
            "market",
            "raf",
        ],
    },
    "finance": {
        "keywords": [
            "borsa",
            "hisse",
            "kur",
            "tahvil",
            "bist",
            "dolar",
            "euro",
            "kap",
            "halka arz",
            "bilanço",
            "faiz oranı",
        ],
    },
    "geopolitical": {
        "keywords": [
            "savaş",
            "yaptırım",
            "nato",
            "güvenlik",
            "jeopolitik",
            "sanctions",
            "ambargo",
            "çatışma",
        ],
    },
    "strategy": {
        "keywords": [
            "strateji",
            "inovasyon",
            "dijital",
            "ai",
            "leadership",
            "disruption",
            "transformation",
            "sürdürülebilirlik",
        ],
    },
    "regulatory": {
        "keywords": [
            "resmi gazete",
            "yönetmelik",
            "kanun",
            "mevzuat",
            "regülasyon",
            "düzenleme",
            "kvkk",
        ],
    },
}


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


def master_keyword_pool() -> tuple[str, ...]:
    """Tüm kategori keyword'lerinin birleşimi (dedupe)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for rule in CATEGORY_RULES.values():
        for keyword in rule["keywords"]:
            normalized = normalize_for_match(keyword)
            if normalized not in seen:
                seen.add(normalized)
                ordered.append(keyword)
    return tuple(ordered)


@lru_cache(maxsize=1)
def _sorted_master_keywords() -> tuple[str, ...]:
    """Uzun keyword'ler önce — çok kelimeli ifadeler için."""
    return tuple(sorted(master_keyword_pool(), key=len, reverse=True))


def find_matching_keywords(
    title: str,
    content: str,
    keywords: Iterable[str] | None = None,
) -> list[str]:
    """Title + body içinde eşleşen keyword'leri döner (case-insensitive, NFC)."""
    haystack = normalize_for_match(f"{title} {content}")
    pool = tuple(keywords) if keywords is not None else _sorted_master_keywords()
    matched: list[str] = []
    seen: set[str] = set()
    for keyword in pool:
        needle = normalize_for_match(keyword)
        if needle not in seen and _keyword_in_haystack(haystack, keyword):
            seen.add(needle)
            matched.append(keyword)
    return matched


def has_master_keyword_match(title: str, content: str) -> bool:
    """Master havuzda ≥1 eşleşme var mı?"""
    return bool(find_matching_keywords(title, content))


CATEGORY_TO_SCHEMA: dict[str, str] = {
    "macro": "news",
    "strategy": "news",
    "regulatory": "news",
    "fmcg": "fmcg",
    "finance": "market",
    "geopolitical": "geo",
    # `default_category` config değerleri (SourceCategory uyumu)
    "turkish_media": "news",
    "official": "news",
    "market": "market",
    "geo": "geo",
}


def resolve_schema_category(category: str) -> str:
    """İçerik kategorisini PostgreSQL schema adına map eder."""
    return CATEGORY_TO_SCHEMA.get(category, "news")


def count_matches_by_category(title: str, content: str) -> dict[str, list[str]]:
    """Kategori başına eşleşen keyword listesi."""
    result: dict[str, list[str]] = {}
    for category, rule in CATEGORY_RULES.items():
        matched = find_matching_keywords(title, content, keywords=rule["keywords"])
        if matched:
            result[category] = matched
    return result


def resolve_content_category(
    title: str,
    content: str,
    *,
    ingest_mode: str,
    default_category: str,
) -> tuple[str, list[str]]:
    """Kategori çözümleme — `Docs/04` §8.4 sırası."""
    all_matched = find_matching_keywords(title, content)

    if ingest_mode == "all":
        return default_category, all_matched

    by_category = count_matches_by_category(title, content)
    if not by_category:
        return default_category, all_matched

    max_count = max(len(keywords) for keywords in by_category.values())
    top_categories = [
        category for category, keywords in by_category.items() if len(keywords) == max_count
    ]

    if len(top_categories) == 1:
        winner = top_categories[0]
        return winner, all_matched

    return default_category, all_matched

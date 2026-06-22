"""`fixtures/keywords.json` seed havuzu bütünlük testleri (Faz 6.3.1).

DB gerektirmez — production-grade seed havuzunun kalite kriterlerini
(`Docs/02` §8) JSON üzerinden doğrular.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from packages.shared.enums import KeywordCategory

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "keywords.json"


@pytest.fixture(scope="module")
def keywords() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, list), "keywords.json bir JSON array olmalıdır."
    assert data, "keywords.json boş olmamalıdır."
    return data


def test_required_top_level_fields(keywords: list[dict[str, Any]]) -> None:
    for item in keywords:
        assert item["term_tr"].strip(), "term_tr boş olamaz."
        assert item["term_en"].strip(), "term_en boş olamaz."
        assert isinstance(item.get("is_active", True), bool)
        assert isinstance(item["categories"], list) and item["categories"], (
            f"{item['term_tr']} en az bir kategori taşımalıdır."
        )


def test_term_length_within_column_limit(keywords: list[dict[str, Any]]) -> None:
    for item in keywords:
        assert len(item["term_tr"]) <= 120
        assert len(item["term_en"]) <= 120


def test_term_tr_lower_unique(keywords: list[dict[str, Any]]) -> None:
    terms = [item["term_tr"].casefold() for item in keywords]
    assert len(terms) == len(set(terms)), "term_tr (lower) mükerrer."


def test_term_en_lower_unique(keywords: list[dict[str, Any]]) -> None:
    terms = [item["term_en"].casefold() for item in keywords]
    assert len(terms) == len(set(terms)), "term_en (lower) mükerrer."


def test_ratings_within_bounds(keywords: list[dict[str, Any]]) -> None:
    for item in keywords:
        for entry in item["categories"]:
            rating = entry["rating"]
            assert isinstance(rating, int) and not isinstance(rating, bool)
            assert 1 <= rating <= 10, f"{item['term_tr']} rating aralık dışı: {rating}"


def test_categories_are_valid_enum_values(keywords: list[dict[str, Any]]) -> None:
    valid = {member.value for member in KeywordCategory}
    for item in keywords:
        for entry in item["categories"]:
            assert entry["category"] in valid


def test_category_not_repeated_within_keyword(keywords: list[dict[str, Any]]) -> None:
    for item in keywords:
        cats = [entry["category"] for entry in item["categories"]]
        assert len(cats) == len(set(cats)), f"{item['term_tr']} aynı kategoriyi tekrar ediyor."


def test_every_category_has_keywords(keywords: list[dict[str, Any]]) -> None:
    covered = {entry["category"] for item in keywords for entry in item["categories"]}
    expected = {member.value for member in KeywordCategory}
    assert covered == expected, f"Eksik kategori(ler): {expected - covered}"


def test_has_multi_category_keyword(keywords: list[dict[str, Any]]) -> None:
    assert any(len(item["categories"]) > 1 for item in keywords), (
        "En az bir çok-kategorili keyword bulunmalıdır."
    )

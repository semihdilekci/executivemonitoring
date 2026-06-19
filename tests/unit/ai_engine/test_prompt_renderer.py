"""PromptRenderer unit testleri."""

from __future__ import annotations

import pytest
from services.ai_engine.exceptions import PromptTemplateRenderError
from services.ai_engine.prompt_renderer import PromptRenderer


@pytest.fixture
def renderer() -> PromptRenderer:
    return PromptRenderer()


def test_render_valid_template(renderer: PromptRenderer) -> None:
    template = "Bülten tipi: {{ digest_type }}\nDönem: {{ date_range }}\n{{ context }}"
    context = {
        "digest_type": "fmcg_weekly",
        "date_range": "2026-06-01 — 2026-06-07",
        "context": "Makale özeti burada.",
    }

    result = renderer.render(template, context)

    assert "fmcg_weekly" in result
    assert "2026-06-01" in result
    assert "Makale özeti burada." in result


def test_render_articles_placeholder(renderer: PromptRenderer) -> None:
    template = "Aşağıdaki makaleleri analiz et:\n\n{{ articles }}"
    context = {"articles": "- Haber 1\n- Haber 2"}

    result = renderer.render_user_prompt(template, context={"articles": context["articles"]})

    assert "Haber 1" in result
    assert "Haber 2" in result


def test_render_missing_variable_raises(renderer: PromptRenderer) -> None:
    template = "Merhaba {{ missing_var }}"

    with pytest.raises(PromptTemplateRenderError, match="eksik değişken"):
        renderer.render(template, {})


def test_render_invalid_syntax_raises(renderer: PromptRenderer) -> None:
    template = "Geçersiz {% if %}"

    with pytest.raises(PromptTemplateRenderError, match="geçersiz"):
        renderer.render(template, {})

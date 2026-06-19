"""Jinja2 tabanlı prompt şablonu render."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError, UndefinedError

from services.ai_engine.exceptions import PromptTemplateRenderError


class PromptRenderer:
    """Prompt şablonlarını güvenli Jinja2 context ile render eder."""

    def __init__(self) -> None:
        self._env = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template: str, context: dict[str, Any]) -> str:
        """Şablonu context ile render eder — eksik değişken kontrollü hata."""
        try:
            compiled = self._env.from_string(template)
            return compiled.render(**context).strip()
        except UndefinedError as exc:
            raise PromptTemplateRenderError(
                f"Prompt şablonunda eksik değişken: {exc}",
            ) from exc
        except TemplateError as exc:
            raise PromptTemplateRenderError(
                f"Prompt şablonu geçersiz: {exc}",
            ) from exc

    def render_user_prompt(
        self,
        user_prompt_template: str,
        *,
        context: dict[str, Any],
    ) -> str:
        """Kullanıcı prompt şablonunu render eder."""
        return self.render(user_prompt_template, context)

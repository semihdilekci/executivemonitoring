"""Anlık etki ("Yıldız'ı nasıl etkiler?") prompt'larını sıkılaştır (Faz 6.5).

Global `newsletter_impact_*` prompt'ları 013'te `ON CONFLICT DO NOTHING` ile
seed edilmişti; mevcut DB'lerde gevşek metinle kalıyor. LLM yanıtları markdown
başlık/tablo/madde işaretleriyle 3-4 cümleyi aşıyor ve gecikme artıyordu. Bu
migration kayıtlı değerleri "düz metin, 3-4 cümle, (1) iş kolu (2) fırsat/risk
(3) aksiyon" yapısıyla günceller. Kod tarafı `digest_service` fallback'leri ve
`max_tokens=512` ile hizalanır.

Dosya adı 017: head `016_translation_infra` olduğundan onun ardından zincirlenir.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_impact_prompt_tighten"
down_revision: str | None = "016_translation_infra"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMPACT_SYSTEM_KEY = "newsletter_impact_system_prompt"
_IMPACT_USER_KEY = "newsletter_impact_user_prompt"

# --- yeni (sıkılaştırılmış) değerler ---
_NEW_SYSTEM_PROMPT = (
    "Sen YıldızHolding üst yönetimine danışmanlık yapan kıdemli bir strateji "
    "analistisin. Tek bir haberin YıldızHolding üzerindeki olası etkisini "
    "değerlendirirsin. SADECE düz metin yaz; markdown, başlık, tablo, madde "
    "işareti, kalın yazı veya emoji KULLANMA. Yanıtın Türkçe, somut, ağdasız "
    "ve en fazla 3-4 cümle olmalıdır."
)
_NEW_USER_PROMPT = (
    "Haber başlığı: {title}\n\nHaber içeriği:\n{content}\n\n"
    "Bu gelişmenin etkisini şu yapıda, kısa ve somut değerlendir: "
    "(1) etkilenen YıldızHolding iş kolu veya markası, "
    "(2) kurumsal/M&A açısından fırsat veya risk, (3) önerilen aksiyon. "
    "En fazla 3-4 cümle, düz metin, ağdasız bir dille."
)

# --- eski (013'te seed edilen) değerler — downgrade için ---
_OLD_SYSTEM_PROMPT = (
    "Sen YıldızHolding üst yönetimine danışmanlık yapan kıdemli bir strateji "
    "analistisin. Tek bir haberin YıldızHolding (gıda, FMCG, perakende, finans, "
    "enerji portföyü) üzerindeki olası etkisini değerlendirirsin. Yanıtın Türkçe, "
    "somut ve yönetici odaklıdır."
)
_OLD_USER_PROMPT = (
    "Haber başlığı: {title}\n\nHaber içeriği:\n{content}\n\n"
    "Bu gelişme YıldızHolding'i nasıl etkiler? Fırsat ve riskleri, ilgili iş "
    "kollarını ve önerilen aksiyonu kısaca açıkla."
)

_UPDATE_SQL = (
    "UPDATE system_settings SET value = to_jsonb(CAST(:value AS text)) "
    "WHERE key = :key"
)


def _apply(pairs: list[tuple[str, str]]) -> None:
    for key, value in pairs:
        op.execute(sa.text(_UPDATE_SQL).bindparams(key=key, value=value))


def upgrade() -> None:
    _apply(
        [
            (_IMPACT_SYSTEM_KEY, _NEW_SYSTEM_PROMPT),
            (_IMPACT_USER_KEY, _NEW_USER_PROMPT),
        ]
    )


def downgrade() -> None:
    _apply(
        [
            (_IMPACT_SYSTEM_KEY, _OLD_SYSTEM_PROMPT),
            (_IMPACT_USER_KEY, _OLD_USER_PROMPT),
        ]
    )

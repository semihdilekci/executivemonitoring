"""Serbest bülten konfig modeli — newsletter_templates + newsletter_sections (Faz 6.5, ADR-0003).

Düz `prompt_templates` iki seviyeli serbest modele taşınır:
- `newsletter_templates` (bülten-seviyesi: editör/özet prompt'ları, aday havuz eşiği)
- `newsletter_sections` (bülten başına N kullanıcı-adlandırmalı bölüm: bölüm özet + Yıldız etki)

Mevcut `prompt_templates` satırları yeni tablolara migrate edilir, ardından tablo düşürülür
(`INSERT … SELECT` → drop, migrate→drop). `digests.digest_type` (enum) → `newsletter_template_id`
(FK SET NULL) + denormalize `newsletter_slug`; `digests.summary` (TEXT, editör özeti) eklenir.
`digest_sections.prompt_template_id` → `newsletter_section_id` (provenance, SET NULL). Anlık
"Yıldız'ı nasıl etkiler?" prompt'u global `system_settings` key'lerine seed'lenir.

Dosya adı 013: head `012_api_key_model` olduğundan onun ardından zincirlenir.

Downgrade kısıtı: `newsletter_templates.slug` yalnızca eski 3 enum değerinden biriyse
(`turkish_media_weekly`/`fmcg_weekly`/`strategy_weekly`) `digests.digest_type`'a geri
dönüştürülebilir. Serbest slug ile oluşturulmuş bültenler downgrade'i bozar (ADR-0003,
breaking redesign — round-trip yalnızca migrate edilmiş veri için garanti).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_newsletter_config"
down_revision: str | None = "012_api_key_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

digest_type_enum = postgresql.ENUM(
    "turkish_media_weekly",
    "fmcg_weekly",
    "strategy_weekly",
    name="digest_type_enum",
    create_type=False,
)

# prompt_templates emekliye ayrılırken bülten-seviyesi editör (özet) prompt'ları kodda yoktu;
# migrate sırasında üretici (production-grade) varsayılanlar sentezlenir. Admin sonradan düzenler.
_DEFAULT_SUMMARY_SYSTEM_PROMPT = (
    "Sen YıldızHolding üst yönetimi (CEO ve yönetim kurulu) için haftalık istihbarat "
    "bülteni hazırlayan kıdemli bir editörsün. Aday haberleri okur, bültene-uygun olanları "
    "seçer, tanımlı bölümlere dağıtır, alakasız olanları elersin. Çıktın Türkçe, net ve "
    "yönetici odaklıdır."
)
_DEFAULT_SUMMARY_USER_PROMPT = (
    "Bülten: {newsletter_name}\nAçıklama: {newsletter_description}\nDönem: {date_range}\n"
    "Bölümler: {sections}\n\nAday haberler:\n{articles}\n\n"
    "Haberleri ilgili bölümlere dağıt, alakasızları ele ve haftanın yönetici özetini üret."
)
_DEFAULT_SECTION_IMPACT_PROMPT = (
    "Bu bölümdeki gelişmelerin YıldızHolding (gıda, FMCG, perakende, finans portföyü) "
    "açısından stratejik etkisini 2-3 cümleyle, yönetici diliyle özetle."
)

# Anlık "Yıldız'ı nasıl etkiler?" — tek global prompt (ADR-0003). Bülten/bölüm başına değil.
IMPACT_SYSTEM_PROMPT = (
    "Sen YıldızHolding üst yönetimine danışmanlık yapan kıdemli bir strateji analistisin. "
    "Tek bir haberin YıldızHolding (gıda, FMCG, perakende, finans, enerji portföyü) "
    "üzerindeki olası etkisini değerlendirirsin. Yanıtın Türkçe, somut ve yönetici odaklıdır."
)
IMPACT_USER_PROMPT = (
    "Haber başlığı: {title}\n\nHaber içeriği:\n{content}\n\n"
    "Bu gelişme YıldızHolding'i nasıl etkiler? Fırsat ve riskleri, ilgili iş kollarını ve "
    "önerilen aksiyonu kısaca açıkla."
)

_IMPACT_SETTINGS = (
    (
        "newsletter_impact_system_prompt",
        IMPACT_SYSTEM_PROMPT,
        "Anlık 'Yıldız'ı nasıl etkiler?' analizi system prompt (global, Faz 6.5)",
    ),
    (
        "newsletter_impact_user_prompt",
        IMPACT_USER_PROMPT,
        "Anlık 'Yıldız'ı nasıl etkiler?' analizi user prompt (global, Faz 6.5)",
    ),
)


def _timestamp_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. newsletter_templates ---
    op.create_table(
        "newsletter_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("date_range_days", sa.Integer(), server_default=sa.text("7"), nullable=False),
        sa.Column("summary_system_prompt", sa.Text(), nullable=False),
        sa.Column("summary_user_prompt", sa.Text(), nullable=False),
        sa.Column("min_content_score", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column("model_preference", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_newsletter_templates_slug"),
        sa.CheckConstraint("min_content_score BETWEEN 0 AND 100", name="ck_newsletter_min_score"),
    )
    op.create_index(
        "idx_newsletter_templates_is_active",
        "newsletter_templates",
        ["is_active"],
        unique=False,
    )

    # --- 2. newsletter_sections ---
    op.create_table(
        "newsletter_sections",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("newsletter_template_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("section_system_prompt", sa.Text(), nullable=False),
        sa.Column("section_user_prompt", sa.Text(), nullable=False),
        sa.Column("impact_prompt", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(
            ["newsletter_template_id"],
            ["newsletter_templates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "newsletter_template_id", "sort_order", name="uq_newsletter_sections_order"
        ),
    )
    op.create_index(
        "idx_newsletter_sections_template_id",
        "newsletter_sections",
        ["newsletter_template_id"],
        unique=False,
    )

    # --- 3. prompt_templates → newsletter_templates (distinct digest_type başına 1 bülten) ---
    op.execute(
        sa.text(
            """
            INSERT INTO newsletter_templates
                (slug, name, description, date_range_days,
                 summary_system_prompt, summary_user_prompt, min_content_score,
                 model_preference, is_active)
            SELECT
                digest_type::text AS slug,
                CASE digest_type::text
                    WHEN 'turkish_media_weekly' THEN 'Türk Medyası Haftalık'
                    WHEN 'fmcg_weekly' THEN 'FMCG Haftalık'
                    WHEN 'strategy_weekly' THEN 'Strateji Haftalık'
                    ELSE digest_type::text
                END AS name,
                '' AS description,
                7 AS date_range_days,
                :summary_system AS summary_system_prompt,
                :summary_user AS summary_user_prompt,
                50 AS min_content_score,
                min(model_preference) AS model_preference,
                bool_or(is_active) AS is_active
            FROM prompt_templates
            GROUP BY digest_type
            """
        ).bindparams(
            summary_system=_DEFAULT_SUMMARY_SYSTEM_PROMPT,
            summary_user=_DEFAULT_SUMMARY_USER_PROMPT,
        )
    )

    # --- 4. prompt_templates satırları → newsletter_sections (section_key → bölüm) ---
    op.execute(
        sa.text(
            """
            INSERT INTO newsletter_sections
                (newsletter_template_id, name, sort_order,
                 section_system_prompt, section_user_prompt, impact_prompt, is_active)
            SELECT
                nt.id AS newsletter_template_id,
                pt.section_key AS name,
                (row_number() OVER (
                    PARTITION BY pt.digest_type
                    ORDER BY pt.version, pt.name
                ) - 1) AS sort_order,
                pt.system_prompt AS section_system_prompt,
                pt.user_prompt_template AS section_user_prompt,
                :impact AS impact_prompt,
                pt.is_active AS is_active
            FROM prompt_templates pt
            JOIN newsletter_templates nt ON nt.slug = pt.digest_type::text
            """
        ).bindparams(impact=_DEFAULT_SECTION_IMPACT_PROMPT)
    )

    # --- 5. digests: digest_type (enum) → newsletter_template_id + newsletter_slug + summary ---
    op.add_column("digests", sa.Column("newsletter_slug", sa.String(length=100), nullable=True))
    op.add_column("digests", sa.Column("newsletter_template_id", sa.UUID(), nullable=True))
    op.add_column("digests", sa.Column("summary", sa.Text(), nullable=True))
    op.execute("UPDATE digests SET newsletter_slug = digest_type::text")
    op.execute(
        """
        UPDATE digests d
        SET newsletter_template_id = nt.id
        FROM newsletter_templates nt
        WHERE nt.slug = d.newsletter_slug
        """
    )
    op.alter_column("digests", "newsletter_slug", nullable=False)
    op.create_foreign_key(
        "fk_digests_newsletter_template_id",
        "digests",
        "newsletter_templates",
        ["newsletter_template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index("idx_digests_digest_type", table_name="digests")
    op.drop_column("digests", "digest_type")
    op.create_index("idx_digests_newsletter_slug", "digests", ["newsletter_slug"], unique=False)

    # --- 6. digest_sections: prompt_template_id → newsletter_section_id ---
    op.execute(
        "ALTER TABLE digest_sections "
        "DROP CONSTRAINT IF EXISTS digest_sections_prompt_template_id_fkey"
    )
    op.alter_column(
        "digest_sections",
        "prompt_template_id",
        new_column_name="newsletter_section_id",
    )
    # Eski provenance prompt_templates'e işaret ediyordu; tablo düşüyor → NULL (snapshot korunur).
    op.execute("UPDATE digest_sections SET newsletter_section_id = NULL")
    op.create_foreign_key(
        "fk_digest_sections_newsletter_section_id",
        "digest_sections",
        "newsletter_sections",
        ["newsletter_section_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- 7. prompt_templates tablosunu düşür ---
    op.drop_index("idx_prompt_templates_is_active", table_name="prompt_templates")
    op.drop_index("idx_prompt_templates_digest_type", table_name="prompt_templates")
    op.drop_table("prompt_templates")

    # --- 8. digest_type_enum tipini düşür (artık kolon kullanmıyor) ---
    digest_type_enum.drop(bind, checkfirst=True)

    # --- 9. global anlık-etki prompt'ları system_settings'e seed ---
    for key, value, description in _IMPACT_SETTINGS:
        op.execute(
            sa.text(
                """
                INSERT INTO system_settings (key, value, description)
                VALUES (:key, to_jsonb(CAST(:value AS text)), :description)
                ON CONFLICT (key) DO NOTHING
                """
            ).bindparams(key=key, value=value, description=description)
        )


def downgrade() -> None:
    bind = op.get_bind()

    # --- 9. system_settings anlık-etki key'lerini kaldır ---
    op.execute(
        "DELETE FROM system_settings "
        "WHERE key IN ('newsletter_impact_system_prompt', 'newsletter_impact_user_prompt')"
    )

    # --- 8. digest_type_enum tipini yeniden oluştur ---
    digest_type_enum.create(bind, checkfirst=True)

    # --- 7. prompt_templates tablosunu yeniden oluştur ---
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("digest_type", digest_type_enum, nullable=False),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("model_preference", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_prompt_templates_name"),
    )
    op.create_index(
        "idx_prompt_templates_digest_type", "prompt_templates", ["digest_type"], unique=False
    )
    op.create_index(
        "idx_prompt_templates_is_active", "prompt_templates", ["is_active"], unique=False
    )

    # newsletter_sections → prompt_templates (slug enum değeriyse geri taşı).
    op.execute(
        """
        INSERT INTO prompt_templates
            (name, digest_type, section_key, system_prompt, user_prompt_template,
             model_preference, is_active, version)
        SELECT
            nt.slug || '_' || ns.name AS name,
            nt.slug::digest_type_enum AS digest_type,
            ns.name AS section_key,
            ns.section_system_prompt AS system_prompt,
            ns.section_user_prompt AS user_prompt_template,
            nt.model_preference AS model_preference,
            ns.is_active AS is_active,
            1 AS version
        FROM newsletter_sections ns
        JOIN newsletter_templates nt ON nt.id = ns.newsletter_template_id
        WHERE nt.slug IN ('turkish_media_weekly', 'fmcg_weekly', 'strategy_weekly')
        """
    )

    # --- 6. digest_sections: newsletter_section_id → prompt_template_id ---
    op.drop_constraint(
        "fk_digest_sections_newsletter_section_id",
        "digest_sections",
        type_="foreignkey",
    )
    op.execute("UPDATE digest_sections SET newsletter_section_id = NULL")
    op.alter_column(
        "digest_sections",
        "newsletter_section_id",
        new_column_name="prompt_template_id",
    )
    op.create_foreign_key(
        "digest_sections_prompt_template_id_fkey",
        "digest_sections",
        "prompt_templates",
        ["prompt_template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- 5. digests: newsletter_* → digest_type ---
    op.drop_index("idx_digests_newsletter_slug", table_name="digests")
    op.drop_constraint("fk_digests_newsletter_template_id", "digests", type_="foreignkey")
    op.add_column("digests", sa.Column("digest_type", digest_type_enum, nullable=True))
    op.execute("UPDATE digests SET digest_type = newsletter_slug::digest_type_enum")
    op.alter_column("digests", "digest_type", nullable=False)
    op.create_index("idx_digests_digest_type", "digests", ["digest_type"], unique=False)
    op.drop_column("digests", "summary")
    op.drop_column("digests", "newsletter_template_id")
    op.drop_column("digests", "newsletter_slug")

    # --- 2 & 1. newsletter tablolarını düşür ---
    op.drop_index("idx_newsletter_sections_template_id", table_name="newsletter_sections")
    op.drop_table("newsletter_sections")
    op.drop_index("idx_newsletter_templates_is_active", table_name="newsletter_templates")
    op.drop_table("newsletter_templates")

"""FMCG Haftalık bültenine iki yeni bölüm — Perakende & Tüketici Trendleri, Operasyon & Ambalaj (Faz 6.5).

`fmcg_weekly` bülteni iki yeni `newsletter_sections` satırıyla genişletilir.
Seed (`fixtures/newsletter_templates.json`) `slug` bazında idempotent ve mevcut
bülteni atladığından, bu bölümler çalışan/var olan veritabanlarına yalnızca bu
migration ile iner.

Bölümler **isim bazında** idempotenttir (`NOT EXISTS`) ve `sort_order` mevcut en
yüksek sıranın bir fazlası olarak **dinamik** atanır — böylece bülten admin
panelinden özelleştirilmiş (bölüm adları/sıraları fixture'dan farklı) olsa bile
`uq_newsletter_sections_order` ihlal edilmeden, listelenen sırayla sona eklenir.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_fmcg_new_sections"
down_revision: str | None = "014_newsletter_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Kullanıcının istediği sırayla — önce tüketici/perakende trendleri, sonra operasyon.
_NEW_SECTIONS = [
    {
        "name": "Perakende & Tüketici Trendleri",
        "section_system_prompt": (
            "Sen Yıldız Holding üst yönetimi için FMCG bülteninin \"Perakende & "
            "Tüketici Trendleri\" bölümünü yazan kıdemli bir analistsin. Sana atanan "
            "haberlerden perakende kanalı dinamiklerini (modern/geleneksel kanal, "
            "indirim marketleri, e-ticaret/hızlı ticaret), özel marka (private label) "
            "penetrasyonunu ve değişen tüketim alışkanlıklarını (sağlık, uygun fiyat "
            "arayışı, paket küçültme) doğrudan ve bilgi içerikli bir dille özetlersin. "
            "Türkçe yazar; şirket adı, ürün ve rakamlarla somut konuşursun. Yalnızca "
            "sağlanan haberlerdeki bilgilere dayan; haberlerde olmayan rakam, isim veya "
            "gelişme uydurma."
        ),
        "section_user_prompt": (
            "Aşağıdaki haberlerden FMCG perakende kanalı gelişmelerini ve tüketici "
            "davranış/trend değişimlerini özetle; kanal kaymalarını, fiyat-değer "
            "algısını ve kategori bazlı talep eğilimlerini öne çıkar. Tek akıcı "
            "paragraf, ağdasız ve somut bir dil kullan; başlık, etiket, madde işareti "
            "veya meta açıklama ekleme. En fazla 4-5 cümle yaz; her cümle somut bir "
            "bilgi taşısın. İlgili gelişme yoksa kısa ve net belirt.\n\n{articles}"
        ),
        "impact_prompt": (
            "Bu trendlerin etkisini şu yapıda, kısa ve somut değerlendir: (1) etkilenen "
            "YıldızHolding kanalı veya kategorisi, (2) talep ve konumlanma açısından "
            "fırsat veya risk, (3) önerilen aksiyon. En fazla 3-4 cümle, ağdasız bir "
            "dille."
        ),
    },
    {
        "name": "Operasyon & Ambalaj",
        "section_system_prompt": (
            "Sen Yıldız Holding üst yönetimi için FMCG bülteninin \"Operasyon & "
            "Ambalaj\" bölümünü yazan kıdemli bir analistsin. Sana atanan haberlerden "
            "tedarik zinciri ve lojistik sürekliliğini, üretim teknolojilerini, ambalaj "
            "inovasyonunu ve sürdürülebilirlik/regülasyon (geri dönüşüm, plastik "
            "vergisi, EPR) gelişmelerini doğrudan ve bilgi içerikli bir dille "
            "özetlersin. Türkçe yazar; şirket adı, ürün ve rakamlarla somut konuşursun. "
            "Yalnızca sağlanan haberlerdeki bilgilere dayan; haberlerde olmayan rakam, "
            "isim veya gelişme uydurma."
        ),
        "section_user_prompt": (
            "Aşağıdaki haberlerden FMCG operasyon, tedarik zinciri ve ambalaj "
            "gelişmelerini özetle; maliyet baskılarını, tedarik risklerini ve "
            "ambalaj/sürdürülebilirlik regülasyonlarını öne çıkar. Tek akıcı paragraf, "
            "ağdasız ve somut bir dil kullan; başlık, etiket, madde işareti veya meta "
            "açıklama ekleme. En fazla 4-5 cümle yaz; her cümle somut bir bilgi "
            "taşısın. İlgili gelişme yoksa kısa ve net belirt.\n\n{articles}"
        ),
        "impact_prompt": (
            "Bu gelişmelerin etkisini şu yapıda, kısa ve somut değerlendir: (1) "
            "etkilenen YıldızHolding operasyonu veya iş kolu, (2) maliyet, tedarik "
            "sürekliliği veya regülasyon uyumu açısından fırsat veya risk, (3) önerilen "
            "aksiyon. En fazla 3-4 cümle, ağdasız bir dille."
        ),
    },
]


def upgrade() -> None:
    insert_sql = sa.text(
        """
        INSERT INTO newsletter_sections
            (newsletter_template_id, name, sort_order,
             section_system_prompt, section_user_prompt, impact_prompt, is_active)
        SELECT
            nt.id,
            :name,
            COALESCE(
                (SELECT max(ns.sort_order) + 1
                 FROM newsletter_sections ns
                 WHERE ns.newsletter_template_id = nt.id),
                0
            ),
            :system_prompt, :user_prompt, :impact_prompt, true
        FROM newsletter_templates nt
        WHERE nt.slug = 'fmcg_weekly'
          AND NOT EXISTS (
              SELECT 1 FROM newsletter_sections ns
              WHERE ns.newsletter_template_id = nt.id
                AND ns.name = :name
          )
        """
    )
    bind = op.get_bind()
    # Sırayla tek tek — her insert bir sonraki max(sort_order)'ı görsün.
    for section in _NEW_SECTIONS:
        bind.execute(
            insert_sql.bindparams(
                name=section["name"],
                system_prompt=section["section_system_prompt"],
                user_prompt=section["section_user_prompt"],
                impact_prompt=section["impact_prompt"],
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM newsletter_sections ns
            USING newsletter_templates nt
            WHERE ns.newsletter_template_id = nt.id
              AND nt.slug = 'fmcg_weekly'
              AND ns.name IN ('Perakende & Tüketici Trendleri', 'Operasyon & Ambalaj')
            """
        )
    )

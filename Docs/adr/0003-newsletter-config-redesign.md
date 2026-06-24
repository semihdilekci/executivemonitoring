# ADR-0003: Serbest Bülten Konfigürasyonu ve 3-Aşamalı Editör Pipeline

**Durum:** Kabul edildi
**Tarih:** 2026-06-24
**Faz:** MVP-0 Faz 6.5 — Bülten İyileştirme

## Bağlam

MVP-0'da bülten üretimi **düz `prompt_templates`** tablosuna dayanıyordu: her satır `digest_type` (sabit 3 enum) + `section_key` + system/user prompt taşıyordu. Bülten bölümleri kodda hardcoded (`SECTION_ORDER`), bülten tipleri `DigestType` enum'una (turkish_media_weekly, fmcg_weekly, strategy_weekly) sabitti.

Yeni ürün gereksinimi:

1. Admin **sınırsız sayıda serbest bülten** tanımlayabilmeli (tip enum'a sabit değil).
2. Her bülten **kullanıcı-adlandırmalı, sınırsız bölüm** içerebilmeli (örn. "Yıldız ve Rakipleri").
3. Üretim **tek LLM çağrısı** yerine **3 aşamalı** olmalı:
   - **Editör LLM** (bülten başına 1): min skor üstü haberleri okur, bültene-uygun olanları seçer, bölümlere dağıtır, alakasızı eler ve haftalık **Bülten Özeti**'ni üretir (Yıldız Holding CEO'su perspektifi).
   - **Bölüm LLM** (bölüm başına 1): editörün o bölüme atadığı haberlerden bölüm özeti + Yıldız etki notu üretir.
   - **Anlık etki** (haber başına, runtime): kullanıcı çekmecedeki "Yıldız'ı nasıl etkiler?" butonuna basınca o tek haber için anlık LLM analizi.
4. Admin tüm bülteni **tek ekrandan** yönetebilmeli.

Düz `prompt_templates` bu iki seviyeli yapıyı (bülten-seviyesi + sınırsız bölüm) ve serbest tipi karşılamıyor.

## Karar

1. **İki seviyeli serbest model:**
   - `newsletter_templates` — bülten-seviyesi konfig: `slug` (serbest tanımlayıcı), `name`, `description` (editör LLM'e gider), `date_range_days` (içerik tarih aralığı), `summary_system_prompt` + `summary_user_prompt` (editör çağrısı), `min_content_score` (0–100).
   - `newsletter_sections` — bülten başına N kullanıcı-adlandırmalı bölüm: `name`, `sort_order`, `section_system_prompt` + `section_user_prompt` (bölüm özet çağrısı), `impact_prompt` (Yıldız etki, bölüm çağrısı).
2. **`DigestType` enum kaldırılır.** Bülten tipi serbest `slug` (string) olur. `digests.digest_type` (enum) yerine `digests.newsletter_template_id` (FK, ON DELETE SET NULL) + denormalize `newsletter_slug` (geçmiş korunur) gelir.
3. **`prompt_templates` tablosu emekliye ayrılır.** Mevcut 3 tipin satırları `newsletter_templates` + `newsletter_sections`'a migrate edilir; tablo migration ile düşürülür. `digest_sections.prompt_template_id` → `newsletter_section_id` (FK, SET NULL) olur.
4. **Haftalık özet** `digests.summary` (TEXT) kolonunda saklanır; editör LLM çıktısıdır.
5. **Editör aday havuzu:** `news.processed_items` üzerinde `relevance_score*100 >= min_content_score` + `date_range_days` tarih aralığı. **Bülten-bazında ön kategori filtresi yok** — ilgi/dağıtım/eleme tamamen editör LLM kararıdır.
6. **Anlık "Yıldız'ı nasıl etkiler?" prompt'u tek global'dir** (`system_settings`: `newsletter_impact_system_prompt`, `newsletter_impact_user_prompt`). Tüm bültenlerde tutarlı; bülten/bölüm başına ayrı değil.

## Sonuçlar

**Olumlu:**
- Admin kod değişmeden sınırsız bülten + bölüm tanımlar.
- Editör LLM ilgisizliği eler → bölümler daha temiz; hardcoded `SECTION_ORDER` / `DIGEST_TYPE_QUERY_CONFIG` kalkar.
- Çıktı modeli (`digest_sections`: `section_title`, `ai_summary`, `impact_note`, `source_references`) korunur — FE render mantığı büyük ölçüde yeniden kullanılır.
- Anlık etki butonu CEO'ya haber-bazında derin analiz sunar.

**Olumsuz / risk:**
- Breaking API: `/prompt-templates` endpoint'leri `/newsletter-templates` ile değişir (MVP-0, prod öncesi — kabul edilebilir).
- `DigestType` enum'a bağlı kod (digest_generator, fixtures, FE labels, cron setting key'leri) geniş dokunulur.
- LLM çağrı sayısı artar (1 editör + N bölüm); maliyet `min_content_score` ve aday havuz boyutuyla kontrol edilir.
- Anlık etki endpoint'i kötüye kullanıma açık → rate-limit zorunlu.

## Reddedilen alternatifler

| Alternatif | Red nedeni |
|------------|------------|
| Düz `prompt_templates`'i genişlet (özel `_summary` section_key'leri) | "Tek ekrandan tüm bülten" UX'i ve sınırsız bölüm zorlaşır; semantik kirlenir |
| 3 sabit tipi koru, sadece zenginleştir | Ürün kararı serbest bülten; sabit enum esnekliği engeller |
| Anlık etki prompt'u bülten/bölüm başına | Şablon ekranını ağırlaştırır; tutarlı global davranış tercih edildi |
| Editör öncesi bülten-bazında kategori ön-filtresi | Editör LLM zaten ilgiyi değerlendiriyor; çift filtre gereksiz karmaşa |
| Tek LLM çağrısında tüm bülten | Uzun context + zayıf bölüm izolasyonu; dağıtım/eleme kalitesi düşer |

## Referanslar

- `Docs/01_DOMAIN_MODEL.md` §2.8–2.10 (NewsletterTemplate, NewsletterSection, Digest)
- `Docs/02_DATABASE_SCHEMA.md` §3, §4.6–4.8
- `Docs/03_API_CONTRACTS.md` §5, §7
- `Docs/04_BACKEND_SPEC.md` §9.2
- `Docs/06_SCREEN_CATALOG.md` S-ADMIN-NEWSLETTERS, S-DIGEST-DETAIL
- `Docs/10_IMPLEMENTATION_ROADMAP.md` Faz 6.5
- `Docs/mimari-kararlar.md` [AI-001]

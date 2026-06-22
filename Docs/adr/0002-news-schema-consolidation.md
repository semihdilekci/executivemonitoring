# ADR-0002: Haber İçeriklerinin `news` Schema'sında Konsolidasyonu

**Durum:** Kabul edildi  
**Tarih:** 2026-06-22  
**Faz:** MVP-0 Faz 6.4 — Haber Schema Konsolidasyonu

## Bağlam

MVP-0'da toplanan tüm içerikler haber/makale formatındadır (RSS, e-posta newsletter, resmi kaynak). Processor pipeline bu haberleri `content_category` (6 keyword kategorisi: macro, finance, fmcg, strategy, geopolitical, regulatory) ile sınıflandırır.

Önceki tasarımda `content_category` → PostgreSQL schema eşlemesi vardı (`finance` → `market`, `fmcg` → `fmcg`, `geopolitical` → `geo` vb.). Bu, schema isimlerinin **gelecek veri tiplerini** ima etmesiyle çelişiyordu:

| Schema | Dokümantasyon anlamı | MVP-0'da fiilen yazılan |
|--------|---------------------|-------------------------|
| `news` | Haber ve medya | macro/strategy/regulatory haberleri |
| `market` | Piyasa ve finansal **veri** (endeks, emtia, makro seri) | finance **haberleri** |
| `fmcg` | FMCG sektör **ölçüm verisi** (Nielsen vb.) | FMCG **haberleri** |
| `geo` | Jeopolitik veri | geopolitical **haberleri** |

MVP-1'de Finnhub/FRED/Yahoo Finance; MVP-3'te Nielsen/Euromonitor gibi kaynaklar **farklı tablo yapıları** ile gelecektir — `processed_items` kopyası değil.

## Karar

1. **Tüm haber niteliği `processed_items` kayıtları** yalnızca `news.processed_items` tablosuna yazılır.
2. **`content_category`** (6 değer) ince sınıflandırma olarak kalır; değişmez.
3. Haber kayıtlarında **`schema_category` kolonu sabit `"news"`** olur (kolon geriye uyum için kalır).
4. **`market`, `fmcg`, `geo`, `transport` schema'ları MVP-0'da haber almaz** — gelecek **veri tipi** (entity shape) için rezerve edilir.
5. **Yeni veri tipi kuralı:** Yeni entity shape → yeni schema + yeni tablo(lar). Yeni bülten → `digest_type` + sorgu filtresi (`content_category`, `source.category`, topic).

## Sonuçlar

**Olumlu:**
- Schema isimleri semantik olarak doğru kalır
- İçerik Arşivi cross-schema `UNION ALL` kalkar
- `content_chunks` → `news.processed_items` native FK mümkün (Faz 6.4 İter 6)
- Digest sorguları `news` + filtre ile sadeleşir
- 6 haber kategorisi (`content_category`) ve keyword havuzu etkilenmez

**Olumsuz / risk:**
- Veri migration: `market`/`fmcg`/`geo` mevcut haber satırları `news`'e taşınmalı (UUID korunur)
- Eski cursor formatı `{market|fmcg|geo}:{uuid}` geçersiz olabilir (admin arşiv — kabul edilebilir)
- `PROCESSED_ITEM_MODELS` ve repository katmanı refactor gerektirir

## Reddedilen alternatifler

| Alternatif | Red nedeni |
|------------|------------|
| 6 haber kategorisi = 6 ayrı schema | Türk Medyası bülteni çok kategorili; UNION karmaşası; 6 bülten MVP-0 kapsamında değil |
| `schema_category` kolonunu kaldırma | Breaking API change; Faz 6.4'te sabit `news` yeterli |
| Tek `public.processed_items` (schema yok) | Gelecek veri tipleri için domain schema ayrımı kaybolur |

## Referanslar

- `Docs/02_DATABASE_SCHEMA.md` §2, §4.4
- `Docs/04_BACKEND_SPEC.md` §8.4
- `Docs/10_IMPLEMENTATION_ROADMAP.md` Faz 6.4
- `Docs/mimari-kararlar.md` [DB-001]

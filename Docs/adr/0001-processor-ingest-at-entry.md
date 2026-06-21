# ADR-0001: Processor Lambda Girişinde Idempotent raw_items Ingest

**Durum:** Kabul edildi  
**Tarih:** 2026-06-21  
**Faz:** MVP-0 Faz 8 — Pipeline Runtime Tamamlama

## Bağlam

Collector Lambda'ları normalize edilmiş makaleyi topic-per-type SQS kuyruklarına yazar. Processor pipeline `raw_items` satırına ihtiyaç duyar (lifecycle + FK). Faz 2.6'da `services/collectors/persistence.ingest_message` ayrı bir SQS consumer stub olarak yazıldı; Faz 3 processor handler aynı kuyruktan okur — **aynı SQS kuyruğunda iki bağımsız Lambda consumer** mimari olarak mümkün değildir (mesaj tek tüketiciye gider).

Faz 6.1 orkestratörü `ingest` aşamasında `raw_items` artışını, `process` aşamasında SQS drain + `processed_items` artışını gözlemler.

## Karar

**Ayrı ingest Lambda yok.** Processor Lambda, SQS trigger handler'ında pipeline zincirinden **önce** idempotent `raw_item` upsert yapar:

1. SQS mesajı deserialize (`ProcessorInput`)
2. `ingest_message(session, body, redis)` — duplicate → no-op, invalid → DLQ path
3. Mevcut dedup → normalize → gate → enrich → score → chunk zinciri
4. `raw_items.status` lifecycle güncellemeleri (mevcut `DbRawItemLifecycle`)

`services/collectors/persistence.py` paylaşılan modül olarak kalır; kod tekrarı yok.

## Sonuçlar

**Olumlu:**
- Diyagram akışı ile uyum: SQS → ingest raw_items → dedup → …
- Faz 6.1 `IngestStageExecutor` collect sonrası `raw_items` artışını gözlemleyebilir (processor invocation ile)
- Tek SQS consumer — at-least-once semantiği korunur

**Olumsuz / risk:**
- Ingest + process aynı Lambda invocation'da — cold start süresi biraz artar (kabul edilebilir MVP-0)
- Processor başarısız olursa `raw_items` pending kalabilir; retry SQS ile idempotent ingest

## Reddedilen alternatifler

| Alternatif | Red nedeni |
|------------|------------|
| Ayrı ingest Lambda + aynı SQS | Mesaj tek consumer'a gider; processor mesaj alamaz |
| Collector'da doğrudan DB insert + SQS | Collector sorumluluğu genişler; VPC/DB erişim collector'a ek yük |
| İki kuyruk (ingest-queue → process-queue) | MVP-0 scope dışı infra karmaşıklığı |

## Referanslar

- `Docs/04_BACKEND_SPEC.md` §8.0
- `Docs/10_IMPLEMENTATION_ROADMAP.md` Faz 8
- `Docs/mimari-kararlar.md` [PIPE-002]

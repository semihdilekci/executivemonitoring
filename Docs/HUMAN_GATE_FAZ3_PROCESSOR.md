# Human Gate — Faz 3: Processor Pipeline

> **Platform:** YıldızHolding Global Intelligence Platform (YGIP)  
> **Faz:** 3 — Processor Pipeline (`Docs/10` §Faz 3, `.cursor/rules/53-phase-03-processor.mdc`)  
> **Branch:** `feature/mvp-0`  
> **Regression audit:** PASS (2026-06-18) — BLOCKER=0, HIGH=0  
> **Onaylayan:** Developer (implementasyon sahibi) + teknik reviewer (PR)

Bu belge, Faz 3'ün **Faz 4'e geçmeden önce** insan tarafından doğrulanması için adım adım kontrol listesidir. Otomatik CI yeşil olsa bile aşağıdaki maddelerin **elle işaretlenmesi** gerekir.

---

## 1. Bu gate neyi doğrular?

Faz 3, collector'dan gelen SQS mesajını alıp şu zincirden geçirir:

```mermaid
flowchart LR
    SQS[SQS mesajı] --> Dedup
    Dedup --> Normalize
    Normalize --> Gate
    Gate -->|DROP| Skip[raw_item PROCESSED\nprocessed_item yok]
    Gate -->|PASS| Enrich
    Enrich --> Score
    Score --> Chunk
    Chunk --> Embed
    Embed --> Persist["{schema}.processed_items\n+ content_chunks"]
```

**Human Gate başarılı sayılır ancak:**

- Tüm **bloklayıcı** maddeler (B1–B8) tamamlanmışsa
- **Bilinçli defer** maddeleri (D1–D3) okunmuş ve kabul edilmişse
- İmzalama bölümü doldurulmuşsa

---

## 2. Ön koşullar (gate öncesi)

| # | Koşul | Nasıl doğrulanır |
|---|--------|------------------|
| P1 | Faz 2 tamamlandı | Collector SQS mesajı + `raw_items` insert çalışıyor |
| P2 | Fix iterasyonları bitti | `@53-phase-03-processor-fix` — BLOCKER/HIGH kapalı |
| P3 | Regression audit PASS | `@phase-controller` — BLOCKER=0, HIGH=0 |
| P4 | Kod PR'da | `services/processor/**` + ilgili testler commit'li, PR açık |

---

## 3. Bloklayıcı kontroller (B1–B8)

Bu maddelerden **biri bile fail** ise gate **GEÇEMEZ**. Her satırı tamamladıkça `[x]` işaretleyin.

### B1 — PR ve CI tam yeşil

```bash
# PR'da GitHub Actions "Test" workflow — tüm adımlar yeşil:
# Lint → Type check → Unit tests → Migrations → Integration tests → Coverage ≥70%
```

**Beklenen:** PR checks kırmızı değil. Özellikle **Integration tests** adımı yeşil olmalı (F-03-007 — yerelde PG yoksa CI kanıtı zorunlu).

- [ ] PR açık ve CI workflow tamamlandı
- [ ] `ruff check .` — CI Lint adımı yeşil
- [ ] `mypy apps/ services/ packages/` — CI Type check yeşil
- [ ] `coverage report --fail-under=70` — CI Coverage check yeşil

---

### B2 — Processor unit testleri ve coverage

```bash
cd /path/to/ExecutiveMonitoring
source .venv/bin/activate   # veya: uv sync

uv run pytest tests/unit/processor/ -v --cov=services/processor --cov-fail-under=80
```

**Beklenen:** Tüm testler pass; `services/processor` line coverage **≥ %80** (Done Definition).

- [ ] 87+ unit test pass
- [ ] Processor modül coverage ≥ %80 (son audit: %87)

---

### B3 — Integration / E2E (PostgreSQL zorunlu)

Yerelde PG yoksa önce:

```bash
docker compose up -d
alembic upgrade head
export DATABASE_URL=postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev
```

Ardından:

```bash
uv run pytest tests/integration/test_pipeline_e2e.py \
  tests/integration/test_embedding_pgvector.py -v
```

**Beklenen:** 5 test **skipped değil**, hepsi pass.

| Test | Ne doğrular |
|------|-------------|
| `test_pipeline_e2e_writes_processed_item_and_chunks` | Tam zincir → `processed_items` + `content_chunks` |
| `test_pipeline_duplicate_message_does_not_create_second_processed_item` | İdempotency — ikinci mesaj çift kayıt üretmez |
| `test_sqs_body_roundtrip_through_handler_orchestrator` | Handler → orchestrator wire |
| `test_similarity_search_orders_by_cosine_distance` | pgvector cosine sıralama |
| `test_embed_and_persist_writes_content_chunks` | Embedding persist |

- [ ] 5/5 integration test pass (skip yok)
- [ ] E2E sonrası DB'de en az 1 `processed_item` ve 1 `content_chunk` satırı (test fixture temizliyor olabilir — test log'unda success görülmeli)

---

### B4 — Done Definition (`53-phase-03-processor.mdc`)

| Madde | Doğrulama | [ ] |
|-------|-----------|-----|
| Fixture SQS → `processed_items` + `content_chunks` | B3 integration testleri | |
| Processor coverage ≥ %80 | B2 komutu | |
| DLQ happy boş; fail path test | `test_handle_sqs_event_*_batch_failure` unit testleri pass | |
| MVP-0 keyword gate + enrich; **LLM yok** | `rg -i "llm|groq|gemini" services/processor/` → yalnızca docstring "sıfır LLM" | |
| Gate DROP → `processed_items` yazılmaz | `test_gate_filtered_no_match_drops` → `result is None` | |

---

### B5 — Pipeline davranış spot-check (unit kanıt)

Aşağıdaki komutlar hızlı regresyon sağlar; hepsi pass olmalı:

```bash
uv run pytest tests/unit/processor/test_dedup.py -q
uv run pytest tests/unit/processor/test_gate.py -q
uv run pytest tests/unit/processor/test_orchestrator.py -q
uv run pytest tests/unit/processor/test_persistence.py -q
```

| Davranış | Kanıt testi | [ ] |
|----------|-------------|-----|
| Dedup Redis SETNX TTL 7 gün (604800) | `test_dedup.py` | |
| Normalizer HTML/NFC/min 10 kelime | `test_normalizer.py` | |
| Scorer `0.6 * keyword + 0.4 * freshness` | `test_scorer.py` | |
| Chunker 512 token / 64 overlap | `test_chunker.py` | |
| Persist fail → `session.rollback()` | `test_orchestrator_persist_failure_rolls_back_and_marks_failed` | |
| Fail SQS → `batchItemFailures` | `test_handle_sqs_event_orchestrator_persist_fail_reports_batch_failure` | |

---

### B6 — Explicit Don'ts

| Yasak | Kontrol | [ ] |
|-------|---------|-----|
| LLM enrichment processor'da | `services/processor/` içinde LLM API çağrısı yok | |
| Digest / chatbot / notification | Faz 3 scope'unda yeni dosya yok | |
| Frontend / yeni collector | PR diff'te `apps/web/`, yeni collector yok | |
| `transport` schema routing (MVP-0) | `resolve_schema_category("transport") == "news"` (`test_enricher.py`) | |

---

### B7 — Güvenlik ve secret hijyeni

| Kontrol | [ ] |
|---------|-----|
| `.env` / API key commit'te yok (`git diff` / PR files) | |
| `OPENAI_API_KEY` log/response'ta sızmıyor (`test_openai_embedding_backend_embed_batch`) | |
| `.env.example` embedding env var'ları mevcut (`OPENAI_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_BATCH_SIZE`) | |

---

### B8 — PR kapsamı ve review

| Kontrol | [ ] |
|---------|-----|
| PR yalnızca Faz 3 + fix kapsamında (scope creep yok) | |
| En az 1 reviewer approve | |
| Self-review checklist (`01-coding-philosophy.mdc`) gözden geçirildi | |

---

## 4. Bilinçli defer — gate'i bloklamaz

Bu maddeler **bilinen ve kabul edilmiş** gap'lerdir. Gate geçebilirsiniz; notları PR veya issue'da saklayın.

| ID | Konu | Karar | [ ] Okundu |
|----|------|-------|------------|
| D1 (F-03-005) | Skip path `raw_items.status = PROCESSED` ama `processed_item` yok | MVP-0 bilinçli semantik: processor mesajı tüketti. `Docs/01` §506 henüz skip notu içermiyor — Faz 4 öncesi veya ayrı docs oturumunda güncellenebilir | |
| D2 (F-03-009) | Processor Lambda CDK/IaC yok | Faz 8 production launch veya ayrı infra iterasyonu | |
| D3 | `source_config_resolver.py` modül coverage ~%60 | Toplam processor %87 ≥ %80; modül bazlı eşik yok | |

---

## 5. Opsiyonel manuel smoke (önerilir)

PG + Redis ayaktayken tek mesajlık uçtan uca deneme:

```bash
# 1. Ortam
docker compose up -d
export DATABASE_URL=postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev
export REDIS_URL=redis://localhost:6379/0
alembic upgrade head

# 2. Kaynak + raw_item (seed veya admin API ile aktif RSS kaynağı olmalı)
# 3. Integration E2E zaten fixture source oluşturuyor — B3 yeterli sayılır

# 4. İsteğe bağlı: orchestrator doğrudan
uv run python -c "
import asyncio, uuid
from datetime import UTC, datetime
from fakeredis.aioredis import FakeRedis
from services.processor.models import ProcessorInput
from services.processor.pipeline_orchestrator import PipelineOrchestrator
# ... (B3 integration testleri bu yolu zaten kapsar)
"
```

**Pratik öneri:** B3 yeşil ise bu bölümü atlayabilirsiniz. İlk kez PG kuruyorsanız B3'ü mutlaka yerelde bir kez çalıştırın.

---

## 6. Gate kararı

### Geçti ✅

Tüm **B1–B8** işaretli + **D1–D3** okundu ve kabul edildi.

| Alan | Değer |
|------|-------|
| Tarih | |
| PR URL | |
| CI run URL | |
| Processor coverage | %___ |
| Integration test | ___/5 pass |
| Onaylayan (developer) | |
| Onaylayan (reviewer) | |

### Geçmedi ❌

| Fail maddesi | Aksiyon |
|--------------|---------|
| | `@53-phase-03-processor-fix` veya yeni fix iterasyonu |
| | |

---

## 7. Gate sonrası adımlar (sırayla)

1. **PR merge** — `feature/mvp-0` branch'ine squash merge (CI yeşil + Human Gate imzalı).
2. **Roadmap işareti** — `Docs/10_IMPLEMENTATION_ROADMAP.md` Faz 3 bölümüne tamamlandı notu (developer onayı ile).
3. **Faz 4 başlangıcı** — `@54-phase-04-ai-engine` + 「Faz 4 — İterasyon 1」.
4. **Defer takibi** — D1 (`Docs/01` skip notu), D2 (processor Lambda IaC) backlog'a.

---

## 8. Hızlı referans — tek komut özeti

```bash
# Gate öncesi tam paket (PG + Redis ayakta varsayımıyla)
uv run ruff check .
uv run mypy services/processor
uv run pytest tests/unit/processor/ --cov=services/processor --cov-fail-under=80 -q
export DATABASE_URL=postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev
alembic upgrade head
uv run pytest tests/integration/test_pipeline_e2e.py tests/integration/test_embedding_pgvector.py -v
```

**Süre tahmini:** CI zaten yeşilse ~15 dk (B3 yerel ilk koşu dahil).

---

_Son güncelleme: 2026-06-18 — regression audit PASS sonrası oluşturuldu._

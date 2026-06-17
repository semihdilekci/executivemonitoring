# 10 — Implementasyon Yol Haritası

> **Platform:** YıldızHolding Global Intelligence Platform (YGIP)
> **Kapsam:** MVP-0 sprint-seviye implementasyon planı, MVP-1/2/3 üst-seviye kapsam
> **Geliştirme modeli:** Cursor Composer AI-destekli geliştirme, her iterasyon tek Composer oturumunda tamamlanır

---

## Geliştirme Prensipleri

**Cursor Composer oturumu = 1 iterasyon.** Her iterasyon tek bir Composer session'ında tamamlanabilecek büyüklüktedir (~3-8 dosya dokunuşu). Iterasyon başlamadan önce Composer'a verilecek context dosyaları her iterasyonda belirtilir.

**Katman izolasyonu.** Bir iterasyonda yalnızca tek bir katmana dokunulur: infra VEYA backend VEYA frontend VEYA mobil. Katmanlar arasında geçiş yapılmaz.

**Sıralı geliştirme.** İterasyonlar numaralandırılmış sırayla geliştirilir. Bir iterasyonun çıktısı sonrakinin girdisidir. Sıra atlanmaz.

**Test gömülü.** Her iterasyona ilgili unit ve integration testleri dahildir. Ayrı "test yazma" iterasyonu yoktur. Cursor instruction'larında "bu modülün testlerini de yaz" kuralı her zaman geçerlidir.

**Branch stratejisi.** Tüm MVP-0 geliştirmesi `feature/mvp-0` branch'inde yapılır. Main'e merge ancak MVP-0 tamamlandığında ve onay alındıktan sonra yapılır.

---

## MVP-0 Faz Haritası

```
Faz 0 — Altyapı ve İskelet
  │
  ▼
Faz 1 — Backend Core
  │
  ▼
Faz 2 — Collector'lar
  │
  ▼
Faz 3 — Processor Pipeline
  │
  ▼
Faz 4 — AI Engine
  │
  ▼
Faz 5 — Bildirim Backend
  │
  ▼
Faz 6 — Web Frontend
  │
  ▼
Faz 7 — Mobil Uygulama
  │
  ▼
Faz 8 — Production Deploy + Launch
```

Her faz tek bir katmana odaklanır. Bir sonraki faza geçmeden önceki fazın tüm iterasyonları tamamlanmış olmalıdır.

---

## Faz 0 — Altyapı ve İskelet

> Öncül: yok
> Ardıl: Faz 1
> Katman: Tooling, DB, Infra

Bu faz hiçbir uygulama kodu içermez. Monorepo iskelet, veritabanı şeması ve AWS dev ortamını kurar.

### 0.1 — Monorepo Scaffold

**Katman:** Tooling
**Çıktı:** Boş ama çalışan monorepo yapısı, tüm linter/formatter/tooling konfigürasyonları

Oluşturulacaklar:
- Kök dizin: `pyproject.toml` (Python workspace), `package.json` (Node workspace), `.gitignore`, `.editorconfig`
- Klasör yapısı: `/apps/api`, `/apps/web`, `/apps/mobile`, `/services/collectors`, `/services/processor`, `/services/ai-engine`, `/packages/shared`, `/infra`, `/fixtures`, `/tests`
- Python tooling: `ruff.toml` (lint + format), `mypy.ini` (type check), `pytest.ini`
- Node tooling: `.eslintrc.js`, `.prettierrc`, `tsconfig.json` (base)
- `.env.example` — tüm environment variable isimleri (değersiz)
- `README.md` — proje açıklaması, kurulum talimatları, klasör yapısı

**Cursor context:** Bu doküman (10_IMPLEMENTATION_ROADMAP.md), CODE-001 klasör yapısı referansı

---

### 0.2 — CI/CD Pipeline

**Katman:** DevOps
**Çıktı:** GitHub Actions workflow, branch protection kuralları

Oluşturulacaklar:
- `.github/workflows/test.yml`: lint (ruff) → typecheck (mypy) → unit test (pytest) → integration test (pytest + PostgreSQL service) → coverage report (fail-under=70)
- `.github/workflows/deploy-dev.yml`: dev ortamına deploy (MVP-0 sonunda aktifleştirilir)
- Branch protection: `main` branch'e doğrudan push yasak, PR + CI pass + 1 approval zorunlu
- `feature/mvp-0` branch oluşturma

**Cursor context:** 0.1 çıktıları

---

### 0.3 — PostgreSQL Schema: Core Tablolar

**Katman:** DB
**Çıktı:** Alembic migration + SQLAlchemy modelleri — core tablolar

Oluşturulacak tablolar:
- `users` — id (UUID), email (unique), full_name, password_hash, role (enum: admin/viewer), is_active, created_at, last_login_at
- `system_settings` — id, key (unique), value (TEXT), description, updated_at
- `password_reset_tokens` — id, user_id (FK), token_hash, expires_at, used_at, created_at
- `audit_logs` — id, event_type, actor_user_id (FK nullable), target_type, target_id, payload (JSONB), created_at

Oluşturulacak dosyalar:
- `packages/shared/models/user.py`
- `packages/shared/models/system_setting.py`
- `packages/shared/models/password_reset_token.py`
- `packages/shared/models/audit_log.py`
- `packages/shared/models/base.py` (SQLAlchemy declarative base, UUID mixin)
- `packages/shared/enums.py` (UserRole enum)
- `alembic/versions/001_core_tables.py`

**Cursor context:** 02_DATABASE_SCHEMA.md (core tablolar bölümü)

---

### 0.4 — PostgreSQL Schema: Veri Tabloları

**Katman:** DB
**Çıktı:** Alembic migration + SQLAlchemy modelleri — veri toplama ve işleme tabloları

Oluşturulacak tablolar:
- `sources` — id, name, source_type (enum: rss/email/api/gov/websocket), config (JSONB), is_active, polling_interval_minutes, last_collected_at, error_count, created_at
- `raw_items` — id, source_id (FK CASCADE), title, content, url, content_hash (unique per source), raw_metadata (JSONB), collected_at
- `processed_items` — id, raw_item_id (FK), source_id (FK), schema_name (enum: news/market/geo/transport/fmcg), title, summary, content, relevance_score, tags (JSONB), processed_at
- `embeddings` — id, processed_item_id (FK), chunk_text, embedding (vector(1536)), created_at
- `api_keys` — id, provider (enum: groq/gemini), key_alias, encrypted_key, is_active, created_at
- `api_usage_logs` — id, api_key_id (FK), model_name, prompt_tokens, completion_tokens, total_tokens, cost_usd, created_at
- pgvector extension yükleme: `CREATE EXTENSION IF NOT EXISTS vector`

Oluşturulacak dosyalar:
- `packages/shared/models/source.py`
- `packages/shared/models/raw_item.py`
- `packages/shared/models/processed_item.py`
- `packages/shared/models/embedding.py`
- `packages/shared/models/api_key.py`
- `packages/shared/models/api_usage_log.py`
- `alembic/versions/002_data_tables.py`

**Cursor context:** 02_DATABASE_SCHEMA.md (veri tabloları bölümü), 0.3 model dosyaları (base.py, enums.py)

---

### 0.5 — PostgreSQL Schema: İçerik Tabloları

**Katman:** DB
**Çıktı:** Alembic migration + SQLAlchemy modelleri — digest, chatbot ve bildirim tabloları

Oluşturulacak tablolar:
- `prompt_templates` — id, digest_type (enum: turkish_media_weekly/fmcg_weekly/strategy_weekly), section_key, system_prompt, user_prompt_template, is_active, updated_at
- `digests` — id, digest_type, title, status (enum: pending/processing/ready/failed), triggered_by (enum: cron/manual), error_message, published_at, created_at
- `digest_sections` — id, digest_id (FK CASCADE), section_key, title, content (TEXT), sort_order, sources_json (JSONB)
- `chat_history` — id, user_id (FK), question, answer, sources (JSONB), tokens_used, created_at
- `notification_logs` — id, user_id (FK), channel (enum: email/push), notification_type, status (enum: sent/failed), error_message, created_at

Oluşturulacak dosyalar:
- `packages/shared/models/prompt_template.py`
- `packages/shared/models/digest.py`
- `packages/shared/models/digest_section.py`
- `packages/shared/models/chat_history.py`
- `packages/shared/models/notification_log.py`
- `alembic/versions/003_content_tables.py`

**Cursor context:** 02_DATABASE_SCHEMA.md (içerik tabloları bölümü), 0.3-0.4 model dosyaları

---

### 0.6 — AWS Dev Ortamı

**Katman:** Infra
**Çıktı:** CDK veya Terraform ile dev ortamı kaynakları

Oluşturulacak kaynaklar:
- RDS PostgreSQL t3.micro (`ygip-dev-db`), pgvector AMI, VPC-internal, backup kapalı
- Upstash Redis (serverless free tier) veya ElastiCache t3.micro
- S3 bucket: `ygip-dev-archive` (ham içerik + digest HTML)
- SQS queue'lar: `ygip-dev-rss-queue`, `ygip-dev-email-queue`, `ygip-dev-gov-queue`, `ygip-dev-api-queue` + her biri için DLQ
- EventBridge: placeholder rule (collector cron'ları Faz 2'de tanımlanır)
- IAM role'lar: Lambda execution role (SQS, S3, RDS, Secrets Manager erişimli), environment-scoped ARN kısıtlaması (`ygip-dev-*`)

> **Not:** E-posta bildirimleri AWS SES değil, kurumsal SMTP ile gönderilir (dev: Gmail SMTP, prod: kurumsal relay). SMTP kimlik bilgileri IaC dışında `.env` / Secrets Manager'da tutulur.

**Cursor context:** `/infra` dizini, AWS servis listesi (bu iterasyon tanımı)

---

## Faz 1 — Backend Core

> Öncül: Faz 0 (DB schema + infra hazır)
> Ardıl: Faz 2
> Katman: Backend (Python/FastAPI)

### 1.1 — FastAPI Boilerplate

**Çıktı:** Çalışan boş API sunucusu, tüm cross-cutting concern'ler yerinde

Oluşturulacaklar:
- `apps/api/main.py` — FastAPI app instance, lifespan (DB connection pool), middleware kayıt
- `apps/api/config.py` — Pydantic Settings (env var okuma)
- `apps/api/middleware/request_id.py` — UUID4 request ID üretim/taşıma
- `apps/api/middleware/rate_limiter.py` — Redis sliding window, endpoint kategori bazlı limit
- `apps/api/exceptions/handlers.py` — global exception handler, error response schema (code, message, request_id)
- `apps/api/exceptions/types.py` — `UnauthorizedException`, `ForbiddenException`, `NotFoundException`, `ConflictException`, `RateLimitException`
- `apps/api/schemas/base.py` — `PaginatedResponse`, `ErrorResponse`, cursor-based pagination parametreleri
- `apps/api/deps/database.py` — async SQLAlchemy session dependency
- `apps/api/routers/health.py` — `GET /health`, `GET /ready` (DB connection check)
- CORS middleware konfigürasyonu (`CORS_ORIGINS` env var'dan)

Testler:
- `tests/unit/core/test_rate_limiter.py`
- `tests/integration/test_health.py`

**Cursor context:** `apps/api/` (boş), `packages/shared/models/base.py`, 04_BACKEND_SPEC.md (middleware bölümü)

---

### 1.2 — Auth: JWT Üretim ve Doğrulama

**Çıktı:** JWT encode/decode, bcrypt hash/verify, FastAPI dependency'ler

Oluşturulacaklar:
- `apps/api/core/security.py` — `create_access_token()`, `create_refresh_token()`, `decode_jwt()`, `hash_password()`, `verify_password()`
- `apps/api/deps/auth.py` — `get_current_user` (JWT decode → DB lookup → User döndür), `require_admin` (rol kontrol)
- `apps/api/schemas/auth.py` — `LoginRequest`, `LoginResponse`, `RefreshRequest`, `TokenResponse`

Testler:
- `tests/unit/core/test_security.py` — JWT üretim/doğrulama, bcrypt hash, expired token, tampered token
- `tests/unit/core/test_password_validation.py` — şifre politikası (min 8, büyük harf, rakam)

**Cursor context:** `apps/api/config.py`, `packages/shared/models/user.py`, `packages/shared/enums.py`

---

### 1.3 — Auth: Login / Refresh / Logout Endpoint'leri

**Çıktı:** Tam çalışan auth akışı

Oluşturulacaklar:
- `apps/api/routers/auth.py` — `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`
- `apps/api/services/auth_service.py` — login logic (email lookup → bcrypt verify → token üretim → audit log), refresh logic (token decode → user active check → yeni token çifti), logout (audit log)
- `apps/api/repositories/user_repository.py` — `get_by_email()`, `update_last_login()`
- Rate limiter: auth endpoint'leri 10 req/dk (IP bazlı)

Testler:
- `tests/integration/test_auth_endpoints.py` — başarılı login, yanlış şifre, pasif kullanıcı, expired refresh, rate limit

**Cursor context:** 1.1 + 1.2 çıktıları, `packages/shared/models/user.py`

---

### 1.4 — User CRUD API

**Çıktı:** Admin kullanıcı yönetim endpoint'leri

Oluşturulacaklar:
- `apps/api/routers/user.py` — `GET /api/v1/users` (admin), `POST /api/v1/users` (admin), `PUT /api/v1/users/{id}` (admin), `DELETE /api/v1/users/{id}` (admin, soft-delete), `GET /api/v1/users/me`, `PUT /api/v1/users/me/password`
- `apps/api/services/user_service.py` — CRUD logic + audit log yazma, duplicate email kontrolü
- `apps/api/repositories/user_repository.py` — `list_paginated()`, `create()`, `update()`, `deactivate()`
- `apps/api/schemas/user.py` — `CreateUserRequest`, `UpdateUserRequest`, `UserResponse`, `UserListResponse`

Testler:
- `tests/integration/test_user_endpoints.py` — admin CRUD, viewer forbidden, duplicate email 409, soft delete

**Cursor context:** 1.1-1.3 çıktıları, `apps/api/deps/auth.py` (require_admin), `packages/shared/models/user.py`

---

### 1.5 — Audit Log Service ve API

**Çıktı:** Event logging helper + admin görüntüleme endpoint'i

Oluşturulacaklar:
- `apps/api/services/audit_service.py` — `log_event(event_type, actor_user_id, target_type, target_id, payload)` helper
- `apps/api/repositories/audit_repository.py` — `create()`, `list_paginated()` (tarih/event_type/actor filtre)
- `apps/api/routers/audit.py` — `GET /api/v1/audit-logs` (admin-only, paginated, filterable)
- `apps/api/schemas/audit.py` — `AuditLogResponse`, `AuditLogListResponse`, filtre parametreleri

Testler:
- `tests/integration/test_audit_endpoints.py` — admin erişim, viewer forbidden, filtre doğrulama
- `tests/unit/services/test_audit_service.py` — log_event çağrısı doğru payload üretiyor

**Cursor context:** 1.1-1.3 çıktıları, `packages/shared/models/audit_log.py`

---

### 1.6 — System Settings API

**Çıktı:** Admin tarafından düzenlenebilir sistem ayarları

Oluşturulacaklar:
- `apps/api/routers/settings.py` — `GET /api/v1/settings` (admin), `PUT /api/v1/settings/{key}` (admin)
- `apps/api/services/settings_service.py` — `get_setting(key, default)`, `update_setting(key, value)` + audit log
- `apps/api/repositories/settings_repository.py` — `get_by_key()`, `upsert()`
- `apps/api/schemas/settings.py` — `SettingResponse`, `UpdateSettingRequest`

Varsayılan ayarlar (seed'de yüklenir):
- `jwt_access_token_minutes`: 60
- `jwt_refresh_token_days`: 30
- `chatbot_similarity_threshold`: 0.7
- `chatbot_top_k`: 5
- `digest_max_articles`: 50

Testler:
- `tests/integration/test_settings_endpoints.py` — get/update, viewer forbidden, audit log yazıldı

**Cursor context:** 1.1-1.5 çıktıları, `packages/shared/models/system_setting.py`

---

### 1.7 — Password Reset API

**Çıktı:** Admin-initiated şifre sıfırlama akışı

Oluşturulacaklar:
- `apps/api/services/password_reset_service.py` — token üretimi (secrets.token_urlsafe), bcrypt hash, mail gönderim trigger, token doğrulama + şifre güncelleme
- `apps/api/routers/password_reset.py` — `POST /api/v1/users/{id}/reset-password` (admin, token üret + mail gönder), `POST /api/v1/auth/reset-password` (public, token + yeni şifre)
- `apps/api/repositories/password_reset_repository.py` — `create()`, `get_valid_token()`, `mark_used()`

Testler:
- `tests/unit/services/test_password_reset.py` — token üretim, expired token, used token
- `tests/integration/test_password_reset_endpoints.py` — tam akış (admin tetikle → token doğrula → şifre güncelle)

**Cursor context:** 1.1-1.5 çıktıları, `packages/shared/models/password_reset_token.py`, mail service (mock)

---

### 1.8 — Seed Script ve Dev Fixture'lar

**Çıktı:** Dev ortamını tek komutla hazırlayan seed script

Oluşturulacaklar:
- `scripts/seed.py` — fixture JSON'lardan veri yükle (idempotent — tekrar çalıştırılabilir)
- `fixtures/users.json` — 1 admin + 2 viewer (şifreleri hash'lenmiş)
- `fixtures/system_settings.json` — tüm varsayılan ayarlar
- `fixtures/prompt_templates.json` — 3 bülten tipi × bölüm şablonları
- `fixtures/sources.json` — 5 RSS + 2 email + 1 gov kaynak (dev URL'ler)

**Cursor context:** Tüm model dosyaları (`packages/shared/models/`), fixture format tanımı

---

## Faz 2 — Collector'lar

> Öncül: Faz 1 (source CRUD, audit log, SQS bağlantısı)
> Ardıl: Faz 3
> Katman: Backend/Service

### 2.1 — BaseCollector Framework

**Çıktı:** Tüm collector'ların implement edeceği abstract class ve yardımcı altyapı

Oluşturulacaklar:
- `services/collectors/base_collector.py` — `BaseCollector` abstract class: `collect(source) → list[CollectorResult]`, retry/backoff logic (exponential, 3 retry), SQS publish helper
- `services/collectors/models.py` — `CollectorResult` dataclass (title, content, url, raw_metadata, collected_at)
- `services/collectors/sqs_publisher.py` — SQS mesaj gönderimi (queue name çözümleme, JSON serialization)
- `services/collectors/error_handler.py` — 3. retry fail → audit log + admin mail bildirimi trigger

Testler:
- `tests/unit/collectors/test_base_collector.py` — retry logic, backoff süreleri, SQS publish mock

**Cursor context:** `services/collectors/` (boş), `packages/shared/models/source.py`, `packages/shared/models/raw_item.py`

---

### 2.2 — Source CRUD API

**Çıktı:** Admin panelinin kullanacağı kaynak yönetim endpoint'leri

Oluşturulacaklar:
- `apps/api/routers/source.py` — `GET /api/v1/sources` (admin), `POST /api/v1/sources` (admin), `PUT /api/v1/sources/{id}` (admin), `DELETE /api/v1/sources/{id}` (admin)
- `apps/api/services/source_service.py` — CRUD + audit log, aktif/pasif toggle, config JSONB validation
- `apps/api/repositories/source_repository.py` — `list_paginated()`, `create()`, `update()`, `delete()`
- `apps/api/schemas/source.py` — `CreateSourceRequest` (source_type + config validation), `SourceResponse`

Testler:
- `tests/integration/test_source_endpoints.py` — admin CRUD, viewer forbidden, config validation

**Cursor context:** 1.1-1.5 çıktıları, `packages/shared/models/source.py`

---

### 2.3 — RSS Collector

**Çıktı:** 35+ RSS kaynağından veri çeken collector

Oluşturulacaklar:
- `services/collectors/rss_collector.py` — `RSSCollector(BaseCollector)`: feedparser ile XML parse, trafilatura ile full-text extraction, content_hash üretimi (SHA-256)
- `services/collectors/handlers/rss_handler.py` — Lambda handler (EventBridge trigger → source listesi çek → collect → SQS publish)
- Fixture: `fixtures/rss/sample_feed.xml`, `fixtures/rss/malformed_feed.xml`

Testler:
- `tests/unit/collectors/test_rss_collector.py` — valid feed parse, malformed XML, empty feed, encoding (UTF-8, ISO-8859-9)

**Cursor context:** `services/collectors/base_collector.py`, `services/collectors/models.py`, fixture XML'ler

---

### 2.4 — Email Collector

**Çıktı:** 9 newsletter kaynağından e-posta çeken collector

Oluşturulacaklar:
- `services/collectors/email_collector.py` — `EmailCollector(BaseCollector)`: IMAP bağlantı, sender filtre, HTML body parse (trafilatura), plain text fallback, content_hash
- `services/collectors/handlers/email_handler.py` — Lambda handler (saatlik EventBridge trigger)
- Fixture: `fixtures/email/sample_newsletter.eml`, `fixtures/email/plain_text_email.eml`

Testler:
- `tests/unit/collectors/test_email_collector.py` — HTML body parse, plain text fallback, sender filtre, encoding

**Cursor context:** `services/collectors/base_collector.py`, IMAP config (mock), fixture EML'ler

---

### 2.5 — Gov Collector

**Çıktı:** TCMB, KAP, Resmi Gazete RSS kaynakları collector

Oluşturulacaklar:
- `services/collectors/gov_collector.py` — `GovCollector(BaseCollector)`: RSS parse (TCMB/KAP/RG formatları), Türkçe karakter normalizasyon, structured metadata extraction
- `services/collectors/handlers/gov_handler.py` — Lambda handler (30 dk EventBridge trigger)

Testler:
- `tests/unit/collectors/test_gov_collector.py` — TCMB feed parse, KAP bildiri parse, Türkçe karakter koruması

**Cursor context:** `services/collectors/base_collector.py`, `services/collectors/rss_collector.py` (pattern referans)

---

### 2.6 — Collector Orchestration

**Çıktı:** EventBridge cron kuralları, Lambda deploy konfigürasyonu, SQS bağlantıları

Oluşturulacaklar:
- `/infra/collectors/` — EventBridge rule tanımları: RSS 15 dk, email 60 dk, gov 30 dk
- Lambda deploy config: her collector tipi için ayrı Lambda fonksiyonu, memory/timeout ayarları
- SQS → DLQ bağlantı doğrulaması
- CloudWatch log group: `/ygip/dev/collectors/`
- `raw_items` tablosuna insert logic (content_hash dedup Redis check → DB insert)

Testler:
- `tests/integration/test_collector_sqs_flow.py` — collector → SQS publish → message receive → raw_items insert (moto mock)

**Cursor context:** `/infra/` dizini, 2.1-2.5 çıktıları, AWS resource tanımları

---

## Faz 3 — Processor Pipeline

> Öncül: Faz 2 (raw_items DB'de, SQS mesajları akıyor)
> Ardıl: Faz 4
> Katman: Backend/Service

### 3.1 — SQS Consumer Framework

**Çıktı:** SQS'ten mesaj alan ve pipeline'a ileten framework

Oluşturulacaklar:
- `services/processor/base_processor.py` — SQS polling loop, message deserialization, pipeline chain pattern (`BaseProcessor.process(item) → ProcessedResult`), error handling + DLQ redirect
- `services/processor/models.py` — `ProcessorInput`, `ProcessorOutput` dataclass'ları
- `services/processor/handlers/processor_handler.py` — Lambda handler (SQS trigger → pipeline chain çalıştır)

Testler:
- `tests/unit/processor/test_base_processor.py` — chain pattern, error handling, DLQ redirect

**Cursor context:** `services/processor/` (boş), `packages/shared/models/raw_item.py`

---

### 3.2 — Dedup Processor

**Çıktı:** Duplicate içerik tespiti ve filtreleme

Oluşturulacaklar:
- `services/processor/dedup_processor.py` — `DedupProcessor(BaseProcessor)`: content_hash hesaplama (SHA-256), Redis `SETNX` ile duplicate check (TTL: 7 gün), duplicate ise pipeline'ı kes

Testler:
- `tests/unit/processor/test_dedup.py` — yeni hash geçer, duplicate hash durur, Redis TTL doğru

**Cursor context:** `services/processor/base_processor.py`, Redis client config

---

### 3.3 — Normalizer

**Çıktı:** Ham metin temizleme ve standartlaştırma

Oluşturulacaklar:
- `services/processor/normalizer.py` — `NormalizerProcessor(BaseProcessor)`: HTML tag strip, Unicode NFC normalizasyon, whitespace cleanup (çoklu boşluk → tek), Türkçe karakter koruması (ışığın, İstanbul), min length filtre (10 kelimeden kısa → at)

Testler:
- `tests/unit/processor/test_normalizer.py` — HTML strip, Unicode, Türkçe karakter, min length

**Cursor context:** `services/processor/base_processor.py`

---

### 3.4 — Gate Processor (Keyword Filter)

**Çıktı:** `ingest_mode` + master keyword havuzu ile filtreleme; eşleşmeyen makaleler işlenmiş veri katmanına yazılmaz

Oluşturulacaklar:
- `services/processor/gate_processor.py` — `GateProcessor(BaseProcessor)`: `sources.config.ingest_mode` okuma (`"all"` → otomatik kabul; `"filtered"` → master keyword havuzu eşleşmesi zorunlu), normalize edilmiş title+body üzerinde case-insensitive arama, eşleşme yoksa DROP (`None` döner)
- `services/processor/keyword_pool.py` — `CATEGORY_RULES` birleşiminden master havuz; gate ve enricher paylaşır

Testler:
- `tests/unit/processor/test_gate.py` — `ingest_mode: "all"` geçer; `filtered` + keyword match geçer; `filtered` + no match DROP; Türkçe NFC eşleşme

**Cursor context:** `services/processor/base_processor.py`, `packages/shared/models/source.py`, `Docs/04` §8.3

---

### 3.5 — Enricher ve Scorer

**Çıktı:** Kategori çözümleme, schema routing, tag extraction ve deterministik `relevance_score`

Oluşturulacaklar:
- `services/processor/enricher.py` — `EnricherProcessor(BaseProcessor)`: `CATEGORY_RULES` ile kategori (en çok eşleşme → `default_category` tie-break → `ingest_mode: "all"` her zaman `default_category`), schema routing (news/market/geo/fmcg), `topics` tag extraction
- `services/processor/scorer.py` — `ScorerProcessor(BaseProcessor)`: `relevance_score` 0.0–1.0 (`keyword_intensity * 0.6 + freshness * 0.4`); source reliability weight yok

Testler:
- `tests/unit/processor/test_enricher.py` — kategori çözümleme, schema routing, `ingest_mode: "all"` default_category
- `tests/unit/processor/test_scorer.py` — deterministik skor, freshness bucket'ları, skor 0.0–1.0 aralığı

**Cursor context:** `services/processor/base_processor.py`, `services/processor/keyword_pool.py`, `packages/shared/enums.py` (schema_name enum)

---

### 3.6 — Chunker ve Embedding

**Çıktı:** Text splitting ve pgvector embedding üretimi

Oluşturulacaklar:
- `services/processor/chunker.py` — `ChunkerProcessor(BaseProcessor)`: text splitting (overlap'lı chunk'lar, max 512 token), chunk metadata (source_id, processed_item_id, chunk_index)
- `services/processor/embedding_service.py` — Embedding API çağrısı (OpenAI text-embedding-3-small veya Cohere embed-v3, model seçimi system_settings'den), batch embedding üretimi, pgvector INSERT

Testler:
- `tests/unit/processor/test_chunker.py` — chunk boyutu doğru, overlap çalışıyor, kısa metin tek chunk
- `tests/integration/test_embedding_pgvector.py` — embedding INSERT → cosine distance sorgu → doğru sıralama (testcontainers pgvector)

**Cursor context:** `services/processor/base_processor.py`, `packages/shared/models/embedding.py`, embedding API referansı

---

### 3.7 — Pipeline Entegrasyonu

**Çıktı:** Tüm processor adımlarının zincir halinde çalıştığı end-to-end pipeline

Oluşturulacaklar:
- `services/processor/pipeline_orchestrator.py` — Pipeline zinciri: SQS message → DedupProcessor → NormalizerProcessor → GateProcessor → EnricherProcessor → ScorerProcessor → ChunkerProcessor → EmbeddingService → processed_items INSERT → embeddings INSERT
- Pipeline konfigürasyonu: adım sırası, hata yönetimi (bir adım fail → loglama, pipeline durur, DLQ'ya yönlendir)
- `raw_items` → `processed_items` mapping logic

Testler:
- `tests/integration/test_pipeline_e2e.py` — fixture raw_item → tam pipeline → processed_item + embedding DB'de doğru yazılmış

**Cursor context:** 3.1-3.6 tüm processor dosyaları, `packages/shared/models/processed_item.py`

---

## Faz 4 — AI Engine

> Öncül: Faz 3 (processed_items + embeddings hazır)
> Ardıl: Faz 5
> Katman: Backend/Service

### 4.1 — LLM Client

**Çıktı:** Groq ve Gemini API çağrı client'ı, round-robin fallback

Oluşturulacaklar:
- `services/ai-engine/llm_client.py` — `LLMClient` class: provider listesi yönetimi, `complete(prompt, system_prompt) → LLMResponse`, round-robin fallback (429/503 → sonraki provider), token counting
- `services/ai-engine/providers/groq_provider.py` — Groq API çağrısı
- `services/ai-engine/providers/gemini_provider.py` — Gemini API çağrısı
- `services/ai-engine/models.py` — `LLMResponse` (text, tokens_used, provider, model, latency_ms)

Testler:
- `tests/unit/ai_engine/test_llm_client.py` — başarılı çağrı, fallback, tüm provider fail → `AllProvidersFailedError`

**Cursor context:** `services/ai-engine/` (boş), API key decryption helper

---

### 4.2 — API Key Management

**Çıktı:** LLM API key CRUD + şifrelenmiş saklama

Oluşturulacaklar:
- `apps/api/routers/api_key.py` — `GET /api/v1/api-keys` (admin), `POST /api/v1/api-keys` (admin), `DELETE /api/v1/api-keys/{id}` (admin)
- `apps/api/services/api_key_service.py` — CRUD + encryption (dev: AES-256-GCM symmetric, prod: AWS KMS envelope), decryption helper (LLM client kullanır), audit log
- `apps/api/schemas/api_key.py` — `CreateApiKeyRequest`, `ApiKeyResponse` (encrypted_key döndürülmez, yalnızca alias + status)

Testler:
- `tests/unit/services/test_api_key_encryption.py` — encrypt → decrypt roundtrip, key hiçbir zaman plain-text loglanmıyor
- `tests/integration/test_api_key_endpoints.py` — CRUD, viewer forbidden

**Cursor context:** 1.1-1.5 backend core, `packages/shared/models/api_key.py`

---

### 4.3 — API Usage Tracking

**Çıktı:** LLM API kullanım logları ve aggregation endpoint'i

Oluşturulacaklar:
- `apps/api/services/api_usage_service.py` — `log_usage(api_key_id, model, prompt_tokens, completion_tokens, cost)`, aggregation sorgular (günlük/haftalık/aylık, key bazlı kırılım)
- `apps/api/routers/api_key.py` (extend) — `GET /api/v1/api-keys/usage` (admin, tarih aralığı + key filtre)
- `apps/api/schemas/api_key.py` (extend) — `ApiUsageResponse`, `ApiUsageSummary`
- LLM client entegrasyonu: her LLM çağrısı sonrası `log_usage()` çağrısı

Testler:
- `tests/integration/test_api_usage_endpoints.py` — usage log yazılıyor, aggregation doğru

**Cursor context:** `services/ai-engine/llm_client.py`, `apps/api/services/api_key_service.py`, `packages/shared/models/api_usage_log.py`

---

### 4.4 — Prompt Template System

**Çıktı:** Bülten tipi bazlı prompt şablon yönetimi

Oluşturulacaklar:
- `apps/api/routers/prompt_template.py` — `GET /api/v1/prompt-templates` (admin), `PUT /api/v1/prompt-templates/{id}` (admin)
- `apps/api/services/prompt_service.py` — CRUD + audit log, Jinja2 template rendering (`{{ articles }}`, `{{ date_range }}`, `{{ digest_type }}`), bülten tipi bazlı şablon çözümleme
- `services/ai-engine/prompt_renderer.py` — `render(template, context) → str`

Testler:
- `tests/unit/ai_engine/test_prompt_renderer.py` — template rendering, eksik değişken handling
- `tests/integration/test_prompt_endpoints.py` — admin CRUD, viewer forbidden

**Cursor context:** `packages/shared/models/prompt_template.py`, Jinja2 referansı

---

### 4.5 — Digest Generator

**Çıktı:** 3 bülten tipini üreten digest engine

Oluşturulacaklar:
- `services/ai-engine/digest_generator.py` — `DigestGenerator` class:
  1. Bülten tipine göre processed_items sorgula (tarih aralığı + schema filtre + relevance_score sıralama)
  2. Prompt template çözümle + render
  3. LLM çağrısı (LLMClient)
  4. LLM çıktısını parse → digest + digest_sections INSERT
  5. Status yönetimi: pending → processing → ready/failed
- `services/ai-engine/digest_parser.py` — LLM çıktısını structured section'lara parse etme (JSON format beklentisi, fallback: regex parse)
- Digest tipleri: `turkish_media_weekly` (Cumartesi), `fmcg_weekly` (Cumartesi), `strategy_weekly` (Cuma)

Testler:
- `tests/unit/ai_engine/test_digest_generator.py` — fixture articles → prompt render → mock LLM → parse → sections doğru
- `tests/unit/ai_engine/test_digest_parser.py` — geçerli JSON, geçersiz JSON fallback, eksik section

**Cursor context:** `services/ai-engine/llm_client.py`, `services/ai-engine/prompt_renderer.py`, `packages/shared/models/digest.py`, `packages/shared/models/digest_section.py`

---

### 4.6 — Digest API

**Çıktı:** Digest listeleme, detay görüntüleme ve manuel tetikleme endpoint'leri

Oluşturulacaklar:
- `apps/api/routers/digest.py` — `GET /api/v1/digests` (authenticated, paginated), `GET /api/v1/digests/{id}` (authenticated, sections dahil), `POST /api/v1/digests/trigger` (admin-only, digest_type seçerek tetikleme)
- `apps/api/services/digest_service.py` — list/detail logic, trigger logic (DigestGenerator çağrısı, async task)
- `apps/api/schemas/digest.py` — `DigestListResponse`, `DigestDetailResponse` (sections dahil), `TriggerDigestRequest`

Testler:
- `tests/integration/test_digest_endpoints.py` — list, detail, trigger (admin vs viewer), empty list

**Cursor context:** 1.1-1.5 backend core, `services/ai-engine/digest_generator.py`, digest model dosyaları

---

### 4.7 — RAG Chatbot

**Çıktı:** Soru → embedding → pgvector search → LLM → yanıt + kaynaklar

Oluşturulacaklar:
- `services/ai-engine/rag_pipeline.py` — `RAGPipeline` class:
  1. Soru → embedding üret (EmbeddingService)
  2. pgvector cosine similarity search (top-k, threshold system_settings'den)
  3. Threshold altı chunk → filtrele
  4. Context window oluştur (chunk'lar + soru)
  5. LLM çağrısı → yanıt
  6. Kaynak referansları çıkar (chunk → processed_item → source)
- `services/ai-engine/context_builder.py` — chunk'ları LLM context'ine formatlama, token limit kontrolü

Testler:
- `tests/unit/ai_engine/test_rag_pipeline.py` — mock embedding + mock pgvector → context oluşturma doğru
- `tests/integration/test_rag_pgvector.py` — gerçek pgvector similarity search (testcontainers)

**Cursor context:** `services/processor/embedding_service.py`, `services/ai-engine/llm_client.py`, `packages/shared/models/embedding.py`

---

### 4.8 — Chatbot API ve History

**Çıktı:** Chatbot endpoint'leri ve sohbet geçmişi kaydı

Oluşturulacaklar:
- `apps/api/routers/chatbot.py` — `POST /api/v1/chatbot/ask` (authenticated), `GET /api/v1/chatbot/history/me` (authenticated, kendi geçmişi), `GET /api/v1/chatbot/history` (admin, tüm kullanıcılar, filtrelenebilir)
- `apps/api/services/chatbot_service.py` — ask logic (RAGPipeline çağrısı → chat_history INSERT → response), rate limit: 20 req/dk
- `apps/api/schemas/chatbot.py` — `AskRequest`, `AskResponse` (answer + sources), `ChatHistoryResponse`

Testler:
- `tests/integration/test_chatbot_endpoints.py` — ask, history/me, history (admin), rate limit, boş soru 422

**Cursor context:** `services/ai-engine/rag_pipeline.py`, 1.1-1.5 backend core, `packages/shared/models/chat_history.py`

---

## Faz 5 — Bildirim Backend

> Öncül: Faz 4 (digest üretimi bildirimi tetikler)
> Ardıl: Faz 6
> Katman: Backend/Service

### 5.1 — SMTP Mail Service

**Çıktı:** Kurumsal SMTP ile HTML mail gönderim servisi

Oluşturulacaklar:
- `services/ai-engine/mail_service.py` — `MailService` class: SMTP client (`aiosmtplib`), HTML template rendering (Jinja2), "yeni rapor hazır" mail template (teaser + platform link), error handling + retry
- Mail template: `templates/digest_notification.html` — başlık, teaser özet, CTA butonu ("Raporu Görüntüle")
- Dev: Gmail SMTP (`smtp.gmail.com:587`, uygulama şifresi); prod: kurumsal SMTP relay (Secrets Manager)

Testler:
- `tests/unit/services/test_mail_service.py` — template render doğru, SMTP mock çağrısı

**Cursor context:** SMTP env config (`SMTP_*`), Jinja2 template

---

### 5.2 — FCM Push Service

**Çıktı:** Firebase Cloud Messaging push gönderim servisi

Oluşturulacaklar:
- `services/ai-engine/push_service.py` — `PushService` class: Firebase Admin SDK, push gönderimi (title, body, data payload), batch gönderim (birden fazla device token), error handling (invalid token → temizle)

Testler:
- `tests/unit/services/test_push_service.py` — push gönderim mock, invalid token handling

**Cursor context:** FCM config, Firebase Admin SDK referansı

---

### 5.3 — FCM Token Registration API

**Çıktı:** Mobil cihaz push token kayıt endpoint'i

Oluşturulacaklar:
- `apps/api/routers/notification.py` — `POST /api/v1/notifications/fcm-token` (authenticated, device token kayıt/güncelle)
- `apps/api/schemas/notification.py` — `RegisterFCMTokenRequest` (token, device_type: ios/android)
- User modeline `fcm_tokens` ilişkisi veya ayrı `device_tokens` tablosu (migration)

Testler:
- `tests/integration/test_notification_endpoints.py` — token kayıt, güncelleme, duplicate handling

**Cursor context:** 1.1-1.5 backend core, `packages/shared/models/user.py`

---

### 5.4 — Bildirim Orchestration

**Çıktı:** Digest ready → alıcı listesi → mail + push gönderim zinciri

Oluşturulacaklar:
- `services/ai-engine/notification_orchestrator.py` — `NotificationOrchestrator` class: digest `ready` event → aktif kullanıcı listesi çek → her kullanıcıya mail (SMTP) + push (FCM) gönder → `notification_logs` INSERT
- EventBridge entegrasyonu: digest üretim Lambda tamamlandığında notification trigger
- Digest cron zamanlaması: Strateji → Cuma 08:00, Türk Medyası + FMCG → Cumartesi 08:00

Testler:
- `tests/unit/services/test_notification_orchestrator.py` — alıcı listesi çözümleme, mail + push mock, notification_log yazımı

**Cursor context:** `services/ai-engine/mail_service.py`, `services/ai-engine/push_service.py`, `packages/shared/models/notification_log.py`

---

### 5.5 — Bildirim Preferences API

**Çıktı:** Admin bildirim yönetim endpoint'leri

Oluşturulacaklar:
- `apps/api/routers/notification.py` (extend) — `GET /api/v1/notifications/preferences` (admin), `PUT /api/v1/notifications/preferences/{user_id}` (admin)
- Bildirim tercihleri: admin belirler, viewer değiştiremez. Alıcı listesi yönetimi, zamanlama ayarları (system_settings üzerinden)

Testler:
- `tests/integration/test_notification_preferences.py` — admin erişim, viewer forbidden

**Cursor context:** 1.1-1.5 backend core, notification router (5.3)

---

## Faz 6 — Web Frontend

> Öncül: Faz 1-5 backend API'leri stabil
> Ardıl: Faz 7
> Katman: Frontend (Next.js)

### 6.1 — Next.js Boilerplate

**Çıktı:** Çalışan boş shell — auth, layout, API client

Oluşturulacaklar:
- `apps/web/` proje yapısı: Next.js + TypeScript + Tailwind CSS
- `lib/api-client.ts` — axios wrapper, base URL config, `withCredentials`, error interceptor (401 → refresh → login, 429 → toast)
- `hooks/use-auth.ts` + `components/providers.tsx` — AuthProvider, useAuth (user, role, isAdmin, login, logout)
- `app/(dashboard)/layout.tsx` — rol bazlı shell: `viewer` → `PillNav` + tam genişlik; `admin` → `Sidebar` + `ml-[260px]`
- `components/layout/pill-nav.tsx` — viewer navigasyonu (Ana Sayfa, Bültenler, AI Chatbot); React Bits pattern, `next/link`, `gsap`
- `components/layout/sidebar.tsx` — **yalnızca admin**; Ana Menü + Yönetim linkleri
- `components/layout/user-menu.tsx` — avatar, çıkış
- `components/layout/admin-topbar.tsx` — admin mobil: hamburger + başlık
- `middleware.ts` — HTTP güvenlik başlıkları (HSTS, CSP, X-Frame-Options), auth redirect (token yoksa /login), `/admin/*` viewer redirect
- `app/layout.tsx` — root layout, AuthProvider wrapper

Testler: Bu iterasyonda test yok (frontend unit test MVP-0'da kapsam dışı — backend API testleri yeterli)

**Cursor context:** `apps/web/` (boş), 04_BACKEND_SPEC.md (API kontratları), 07_SECURITY_IMPLEMENTATION.md (CSP, cookie, CORS)

---

### 6.2 — Login ve Şifre Sıfırlama

**Çıktı:** Login page, reset-password page

Oluşturulacaklar:
- `app/(auth)/login/page.tsx` — email + şifre formu, hata state'leri, rate limit feedback, login sonrası redirect
- `app/(auth)/reset-password/[token]/page.tsx` — URL token → yeni şifre formu, başarı/hata state'leri
- Cookie handling: login response'dan httpOnly cookie set (API proxy route veya backend Set-Cookie)

**Cursor context:** `lib/api-client.ts`, `lib/auth-context.tsx`, auth API kontratları

---

### 6.3 — Viewer: Ana Sayfa (Executive Brief)

**Çıktı:** Günün özeti + okunmamış bülten teaser'ları

Oluşturulacaklar:
- `app/(dashboard)/page.tsx` — Executive Brief kartı, en fazla 3 okunmamış teaser, "Tüm bültenleri gör" → `/digests`, chatbot kısayolu
- `components/home/executive-brief.tsx` — brief API + istatistik bandı
- `hooks/use-brief.ts` — `GET /briefs/today`

**Cursor context:** 6.1 çıktıları, brief API kontratları

---

### 6.3b — Viewer: Bülten Listesi

**Çıktı:** Kronolojik digest listesi (S-DIGESTS-LIST)

Oluşturulacaklar:
- `app/(dashboard)/digests/page.tsx` — yeni/önceki bülten bölümleri, tip filtre, cursor pagination
- `components/digest/digest-card.tsx` — bülten tipi badge, teaser, Yıldız etki bandı, ReadToggle
- `hooks/use-digests.ts` — React Query ile digest list fetching

**Cursor context:** 6.1 çıktıları, digest API kontratları (`GET /digests`)

---

### 6.4 — Viewer: Rapor Detay

**Çıktı:** Digest section'larını gösteren detay sayfası

Oluşturulacaklar:
- `app/(dashboard)/digests/[id]/page.tsx` — digest başlık, tarih, section'lar (sıralı), haber linkleri (tıklanabilir), "Yıldız için" etki notları (vurgulu kutu)
- `components/digest/digest-section.tsx` — section başlık, içerik render, kaynak referansları
- Print-friendly layout (CSS @media print)

**Cursor context:** 6.1-6.3 çıktıları, digest API kontratları (`GET /digests/{id}`)

---

### 6.5 — Viewer: AI Chatbot

**Çıktı:** Chat interface

Oluşturulacaklar:
- `app/(dashboard)/chatbot/page.tsx` — sohbet arayüzü, mesaj gönder/al, scroll-to-bottom
- `components/chatbot/chat-message.tsx` — kullanıcı/bot mesaj balonu, loading indicator
- `components/chatbot/source-card.tsx` — kaynak referans kartları (başlık, URL, skor)
- Rate limit feedback: 429 → "Lütfen biraz bekleyin" toast

**Cursor context:** 6.1 çıktıları, chatbot API kontratları (`POST /chatbot/ask`)

---

### 6.6 — Admin: Kullanıcı Yönetimi

**Çıktı:** Kullanıcı CRUD sayfası

Oluşturulacaklar:
- `app/(dashboard)/admin/users/page.tsx` — kullanıcı listesi tablosu (email, ad, rol, durum, son giriş), pagination
- `components/admin/user-form-modal.tsx` — oluştur/düzenle modal (email, ad, rol seçimi, aktif/pasif), şifre sıfırlama butonu
- Confirmation dialog: kullanıcı pasif yapma/silme onayı

**Cursor context:** 6.1 çıktıları, user API kontratları (`GET/POST/PUT/DELETE /users`)

---

### 6.7 — Admin: Kaynak Yönetimi

**Çıktı:** Kaynak CRUD sayfası

Oluşturulacaklar:
- `app/(dashboard)/admin/sources/page.tsx` — kaynak listesi tablosu (ad, tip, durum, son çekim, hata sayısı), filtre (tipe göre)
- `components/admin/source-form-modal.tsx` — oluştur/düzenle modal (ad, tip seçimi, config JSON editör, polling interval), aktif/pasif toggle
- Son çekim durumu badge: başarılı (yeşil), hata (kırmızı), beklemede (gri)

**Cursor context:** 6.1 çıktıları, source API kontratları

---

### 6.8 — Admin: Prompt, API Key, Ayarlar

**Çıktı:** Prompt editor, API key yönetimi, sistem ayarları sayfaları

Oluşturulacaklar:
- `app/(dashboard)/admin/prompt-templates/page.tsx` — bülten tipi bazlı şablon listesi, inline editor (system_prompt + user_prompt_template), kaydet butonu
- `app/(dashboard)/admin/api-keys/page.tsx` — API key listesi (alias, provider, durum), ekle/sil, kullanım grafiği (recharts: günlük token tüketimi, key bazlı kırılım)
- `components/admin/usage-chart.tsx` — recharts BarChart/LineChart

**Cursor context:** 6.1 çıktıları, prompt/api-key/settings API kontratları

---

### 6.9 — Admin: Audit Log, Sohbet Geçmişi, Bildirim

**Çıktı:** Kalan admin sayfaları

Oluşturulacaklar:
- `app/(dashboard)/admin/audit-logs/page.tsx` — filtrelenebilir tablo (tarih aralığı, event type, actor), pagination, payload detay expandable row
- `app/(dashboard)/admin/chat-history/page.tsx` — kullanıcı bazlı chatbot geçmişi, soru/yanıt listesi, tarih filtre
- `app/(dashboard)/admin/notifications/page.tsx` — bildirim alıcı listesi, zamanlama + JWT/chatbot ayarları (`Docs/05` §4 route tablosu)

**Cursor context:** 6.1 çıktıları, audit/chatbot-history/notification API kontratları

---

## Faz 7 — Mobil Uygulama

> Öncül: Faz 6 (API kontratları web'de valide edilmiş)
> Ardıl: Faz 8
> Katman: Mobil (React Native)

### 7.1 — React Native Boilerplate

**Çıktı:** Çalışan boş mobil uygulama shell'i

Oluşturulacaklar:
- `apps/mobile/` proje yapısı: Expo + TypeScript
- Navigation: React Navigation (Stack + Tab navigator)
- Auth context: login/logout, expo-secure-store (access + refresh token), auto-refresh interceptor
- API client: axios wrapper, base URL, Bearer header injection
- Tab bar: Ana Sayfa, Bültenler, Chatbot (viewer); + Yönetim (admin)

**Cursor context:** `apps/mobile/` (boş), `apps/web/lib/api-client.ts` (API kontrat referansı)

---

### 7.2 — Login, Ana Sayfa ve Bülten Listesi

**Çıktı:** Login screen + Executive Brief + bülten listesi

Oluşturulacaklar:
- `screens/LoginScreen.tsx` — email + şifre formu, hata state, expo-secure-store token kayıt
- `screens/HomeScreen.tsx` — Executive Brief + okunmamış teaser'lar
- `screens/DigestsScreen.tsx` — FlatList digest kartları, pull-to-refresh, tip filtre, infinite scroll
- `components/DigestCard.tsx` — bülten tipi badge, tarih, başlık

**Cursor context:** 7.1 çıktıları, digest API kontratları

---

### 7.3 — Rapor Detay ve Chatbot

**Çıktı:** Digest detay ve chatbot ekranları

Oluşturulacaklar:
- `screens/DigestDetailScreen.tsx` — ScrollView, section render, haber linkleri (Linking.openURL), "Yıldız için" etki notları
- `screens/ChatbotScreen.tsx` — chat UI (FlatList inverted), mesaj gönder/al, kaynak referans kartları, loading indicator
- `components/ChatMessage.tsx` — kullanıcı/bot mesaj balonu
- `components/SourceCard.tsx` — kaynak referans kartı

**Cursor context:** 7.1-7.2 çıktıları, chatbot API kontratları

---

### 7.4 — Push Notification Entegrasyonu

**Çıktı:** FCM push bildirim altyapısı

Oluşturulacaklar:
- `lib/notifications.ts` — expo-notifications ile permission request, FCM token alma, token registration API çağrısı (`POST /notifications/fcm-token`)
- Foreground notification handler: toast/banner göster
- Background notification handler: bildirime tıklayınca ilgili digest detayına navigate
- iOS + Android platform-specific konfigürasyon (app.json / app.config.js)

**Cursor context:** 7.1-7.3 çıktıları, notification API kontratları

---

## Faz 8 — Production Deploy ve Launch

> Öncül: Faz 0-7 tamamlanmış
> Ardıl: MVP-1
> Katman: Infra, Operasyon

### 8.1 — Production AWS Ortamı

**Çıktı:** Prod ortamı kaynakları

Oluşturulacaklar:
- Prod RDS PostgreSQL: t3.micro (MVP-0), DeletionProtection: true, automated daily backup, 7 gün retention, PITR aktif
- Prod S3: `ygip-prod-archive`
- Prod SQS: tüm queue'lar + DLQ'lar (`ygip-prod-*`)
- Kurumsal SMTP relay yapılandırması (Secrets Manager `ygip/prod/smtp`)
- Domain + SSL: `ygip.yildizholding.com` + ACM sertifika + CloudFront dağıtımı
- IAM role'lar: prod-scoped ARN kısıtlaması (`ygip-prod-*`)

**Cursor context:** `/infra/` dizini, 0.6 dev ortamı (prod karşılıkları)

---

### 8.2 — Secret Migration

**Çıktı:** Tüm secret'lar AWS Secrets Manager'da

Oluşturulacaklar:
- Secrets Manager'da secret oluşturma: JWT_SECRET_KEY, DATABASE_URL, REDIS_URL, ENCRYPTION_KEY, SMTP config, FCM service account
- Lambda/ECS IAM role'larına Secrets Manager read erişimi
- Application config güncelleme: prod ortamda `.env` yerine Secrets Manager'dan okuma
- KMS CMK oluşturma (LLM API key encryption için)

**Cursor context:** 07_SECURITY_IMPLEMENTATION.md (secret yönetimi bölümü), `/infra/`

---

### 8.3 — Smoke Test ve Performans

**Çıktı:** Production-ready doğrulama

Yapılacaklar:
- Smoke test: login → ana sayfa (brief) → bülten listesi → detay → chatbot soru/yanıt → logout (web + mobil)
- Collector cycle test: 35+ kaynak × 15 dk cycle → raw_items DB'de
- Pipeline test: raw_items → processed_items → embeddings akışı tamamlanıyor
- Digest üretim test: manuel trigger → digest ready → mail + push bildirimi
- Rate limit doğrulama: auth 10/dk, chatbot 20/dk, genel 100/dk
- Performans ölçümü: digest üretim süresi, chatbot yanıt süresi, API response time p95

---

### 8.4 — Prod Seed ve Kullanıcı Oluşturma

**Çıktı:** Platform kullanıma hazır

Yapılacaklar:
- Production source'lar: 35+ RSS, 9 email, 3 gov kaynağı (gerçek URL'ler ve config'ler)
- Prompt şablonları: 3 bülten tipi × bölüm şablonları (Türkçe, üst yönetim diline uygun)
- Sistem ayarları: production varsayılanları
- İlk admin kullanıcısı oluşturma
- 5-10 üst yönetim kullanıcısı oluşturma (CEO ofisi, CFO, strateji direktörleri)
- LLM API key'leri ekleme (Groq + Gemini)

---

### 8.5 — Audit Archive Lambda

**Çıktı:** 90 gün → S3 arşivleme otomatik job'ı

Oluşturulacaklar:
- `services/maintenance/audit_archiver.py` — Lambda fonksiyonu: 90 günden eski audit_logs → S3 JSON Lines export → batch delete
- EventBridge: her ayın 1'i 05:00 TR cron
- S3 path pattern: `s3://ygip-prod-archive/audit-logs/{YYYY}/{MM}/audit_{timestamp}.jsonl`

Testler:
- `tests/unit/maintenance/test_audit_archiver.py` — date filtre, S3 write mock, batch delete

**Cursor context:** `packages/shared/models/audit_log.py`, S3 client config

---

## MVP-1 — Piyasa Verisi ve Alarm Motoru (Üst Seviye)

> Öncül: MVP-0 canlı ve stabil
> Tahmini kapsam: 2-3 sprint

**Yeni collector'lar:** Finnhub (hisse/kur, 5 dk), FRED (makro, günlük), FAO (gıda fiyat endeksi, haftalık), Yahoo Finance (emtia vadeli, 5 dk). Tümü `BaseCollector` implement eder, REST API tipi.

**Alarm motoru:** Admin panelinden kural tanımlama (kaynak + metrik + operatör + eşik). Eşik aşımında anlık push + mail. Örnek: "USD/TRY > 38.00 → bildirim", "TCMB faiz kararı → bildirim".

**Dashboard zenginleştirme:** Piyasa verileri için grafik widget'ları (recharts), trend göstergeleri, alarm geçmişi sayfası.

**Monitoring:** CloudWatch alarm eşikleri, Grafana kurulumu (opsiyonel).

**RDS:** t3.small'a upgrade, backup stratejisi detayı.

---

## MVP-2 — Long-Running Collector'lar ve Harita (Üst Seviye)

> Öncül: MVP-1 canlı
> Tahmini kapsam: 3-4 sprint

**WebSocket collector'lar:** AIS (gemi takibi), USGS (deprem), OpenSky (uçak). ECS Fargate always-on servis olarak çalışır. `BaseCollector` WebSocket varyantı.

**Periyodik API collector'lar:** ACLED (çatışma), GDELT BigQuery (medya), GPSJam (GPS bozma), NASA FIRMS (yangın).

**RAG pipeline genişletme:** Yeni veri kaynaklarından embedding üretimi, chatbot context zenginleştirme.

**AI anomali tespiti:** processed_items üzerinde istatistiksel anomali algılama (z-score, trend kırılma), anomali → alarm.

**Harita görünümü:** Leaflet veya Mapbox ile geo-tagged veriler (gemi pozisyonu, deprem, yangın, çatışma) harita üzerinde görselleştirme.

---

## MVP-3 — Ücretli Kaynaklar ve SAP Entegrasyonu (Üst Seviye)

> Öncül: MVP-2 canlı, sözleşmeler tamamlanmış
> Tahmini kapsam: 2-3 sprint
> Kritik bağımlılık: §18 açık kararlar (I-OPEN-1, I-OPEN-2, I-OPEN-3, I-OPEN-4) kapanmış olmalı

**Euromonitor:** Passport API entegrasyonu, FMCG pazar verisi collector.

**NIQ:** Snowflake Secure Data Sharing ile bulk veri çekimi, ConnectAI/Optiq Bridge RAG entegrasyonu.

**Oxford Economics:** EPRE API, makroekonomik tahmin verisi.

**SAP/ERP:** YH IT ile koordineli iç entegrasyon. Nightly sync veya event-driven (açık karar I-OPEN-4 kapanınca netleşir). Satış, stok, finansal veri.

---

*Bu doküman YıldızHolding Global Intelligence Platform mimari kararlarından türetilmiştir. Kararlar değiştiğinde doküman yeniden üretilir.*

# 02 — Database Schema

## 1. Genel İlkeler

Birincil veritabanı PostgreSQL'dir. pgvector extension MVP-0 kurulumunda yüklenir. Tüm veritabanı erişimi SQLAlchemy ORM parametrik sorguları ile yapılır; raw SQL yasaktır.

### Naming Convention

| Öğe | Kural | Örnek |
|-----|-------|-------|
| Tablo adı | `snake_case`, çoğul | `raw_items`, `digest_sections` |
| Kolon adı | `snake_case` | `source_id`, `created_at` |
| Primary key | `id` (UUID) | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| Foreign key | `{referenced_table_singular}_id` | `source_id`, `user_id`, `digest_id` |
| Index | `idx_{tablo}_{kolon(lar)}` | `idx_raw_items_source_id_content_hash` |
| Unique constraint | `uq_{tablo}_{kolon(lar)}` | `uq_raw_items_source_id_content_hash` |
| Check constraint | `ck_{tablo}_{kural}` | `ck_processed_items_relevance_range` |
| Enum type | `{tablo_singular}_{kolon}_enum` | `source_status_enum`, `user_role_enum` |

### Ortak Kurallar

- Tüm tablolarda primary key `id UUID DEFAULT gen_random_uuid()` olarak tanımlanır. Tek istisna: `system_settings` tablosu (`key VARCHAR(100)` PK).
- Zaman damgaları `TIMESTAMPTZ` (timezone-aware) olarak saklanır. Uygulama katmanı UTC kullanır; frontend kullanıcı timezone'una çevirir.
- `created_at` alanı olan her tabloda `DEFAULT now()` uygulanır.
- `updated_at` alanı olan her tabloda SQLAlchemy `onupdate=func.now()` trigger'ı kullanılır.
- Boolean alanlar `NOT NULL` ve explicit `DEFAULT` ile tanımlanır.
- JSONB alanlar boş olabilecekse `DEFAULT '{}'::jsonb` veya `DEFAULT '[]'::jsonb` ile tanımlanır.

---

## 2. Schema Bölümleme

PostgreSQL schema'ları veri kategorisine göre ayrılır. Ortak tablolar `public` schema'da kalır; domain-specific processed data kendi schema'sında tutulur.

| Schema | İçerik | Tablolar |
|--------|--------|---------|
| `public` | Ortak sistem tabloları | `users`, `sources`, `raw_items`, `content_chunks`, `digests`, `digest_sections`, `prompt_templates`, `api_keys`, `api_usage_logs`, `chat_history`, `audit_logs`, `notification_preferences`, `password_reset_tokens`, `system_settings`, `alarms`, `alarm_events` |
| `news` | Haber ve medya verisi | `news.processed_items` |
| `market` | Piyasa ve finansal veri | `market.processed_items` |
| `geo` | Jeopolitik veri | `geo.processed_items` |
| `transport` | Lojistik ve ulaşım verisi | `transport.processed_items` |
| `fmcg` | FMCG sektör verisi | `fmcg.processed_items` |

Schema bölümleme yalnızca `processed_items` tablosuna uygulanır. Her schema'daki `processed_items` tablosu aynı kolon yapısına sahiptir. Processor pipeline, `schema_category` alanına göre ilgili schema'ya yazar. Sorgularda schema-qualified tablo adı kullanılır: `news.processed_items`, `market.processed_items` vb.

Schema oluşturma migration'ın ilk adımıdır:

```sql
CREATE SCHEMA IF NOT EXISTS news;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS geo;
CREATE SCHEMA IF NOT EXISTS transport;
CREATE SCHEMA IF NOT EXISTS fmcg;
```

---

## 3. Enum Type Tanımları

Tüm enum'lar PostgreSQL native enum olarak tanımlanır. SQLAlchemy'de `sqlalchemy.Enum` ile eşleştirilir.

```sql
CREATE TYPE user_role_enum AS ENUM ('admin', 'viewer');
CREATE TYPE source_type_enum AS ENUM ('rss', 'email', 'rest_api', 'websocket', 'gov');
CREATE TYPE source_status_enum AS ENUM ('active', 'inactive', 'error');
CREATE TYPE source_category_enum AS ENUM ('turkish_media', 'fmcg', 'strategy', 'official', 'market', 'geo', 'transport');
CREATE TYPE raw_item_status_enum AS ENUM ('pending', 'processing', 'processed', 'failed');
CREATE TYPE digest_type_enum AS ENUM ('turkish_media_weekly', 'fmcg_weekly', 'strategy_weekly');
CREATE TYPE digest_status_enum AS ENUM ('generating', 'ready', 'failed');
CREATE TYPE api_provider_enum AS ENUM ('groq', 'gemini');
```

---

## 4. Tablo Tanımları

### 4.1 users

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            user_role_enum NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ,

    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);
```

### 4.2 sources

```sql
CREATE TABLE sources (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                      VARCHAR(255) NOT NULL,
    source_type               source_type_enum NOT NULL,
    config                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    polling_interval_minutes  INTEGER NOT NULL,
    status                    source_status_enum NOT NULL DEFAULT 'active',
    last_fetched_at           TIMESTAMPTZ,
    error_count               INTEGER NOT NULL DEFAULT 0,
    category                  source_category_enum NOT NULL,
    target_phase              VARCHAR(10) NOT NULL,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sources_status ON sources (status);
CREATE INDEX idx_sources_source_type ON sources (source_type);
CREATE INDEX idx_sources_category ON sources (category);
```

**`config` JSONB — MVP-0 zorunlu alanlar (seed/migration verisi):**

| Alan | Tip | Açıklama |
| ---- | --- | -------- |
| `ingest_mode` | `"all"` \| `"filtered"` | Keyword gate davranışı (`Docs/04` §8.3) |
| `default_category` | string | Kategori routing fallback |

Tip-spesifik alanlar (`feed_url`, `imap_host`, vb.) collector tipine göre eklenir. Örnek:

```json
{
  "feed_url": "https://bloomberght.com/rss",
  "ingest_mode": "filtered",
  "default_category": "finance"
}
```

```json
{
  "feed_url": "https://foodnavigator.com/rss",
  "ingest_mode": "all",
  "default_category": "fmcg"
}
```

Mevcut `config` JSONB kolonu şema değişikliği gerektirmez; seed (`fixtures/sources.json`) ve admin API üzerinden `ingest_mode` + `default_category` doldurulur.

### 4.3 raw_items

```sql
CREATE TABLE raw_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id     VARCHAR(512) NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    title           TEXT,
    raw_content     TEXT NOT NULL,
    raw_metadata    JSONB DEFAULT '{}'::jsonb,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          raw_item_status_enum NOT NULL DEFAULT 'pending',
    error_message   TEXT,

    CONSTRAINT uq_raw_items_source_id_content_hash UNIQUE (source_id, content_hash)
);

CREATE INDEX idx_raw_items_source_id ON raw_items (source_id);
CREATE INDEX idx_raw_items_status ON raw_items (status);
CREATE INDEX idx_raw_items_fetched_at ON raw_items (fetched_at);
CREATE INDEX idx_raw_items_content_hash ON raw_items (content_hash);
```

**ON DELETE davranışı:** Source silindiğinde ilişkili raw_items CASCADE ile silinir. Source silme admin onayı gerektirir.

### 4.4 processed_items (schema-partitioned)

Her schema (`news`, `market`, `geo`, `transport`, `fmcg`) için aynı yapı:

```sql
CREATE TABLE {schema}.processed_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_item_id       UUID NOT NULL REFERENCES public.raw_items(id) ON DELETE CASCADE,
    source_id         UUID NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
    title             TEXT NOT NULL,
    clean_content     TEXT NOT NULL,
    summary           TEXT,
    language          VARCHAR(5) NOT NULL,
    relevance_score   FLOAT NOT NULL,
    topics            JSONB NOT NULL DEFAULT '[]'::jsonb,
    entities          JSONB NOT NULL DEFAULT '[]'::jsonb,
    published_at      TIMESTAMPTZ,
    processed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    schema_category   VARCHAR(50) NOT NULL,

    CONSTRAINT uq_{schema}_processed_items_raw_item_id UNIQUE (raw_item_id),
    CONSTRAINT ck_{schema}_processed_items_relevance_range CHECK (relevance_score >= 0 AND relevance_score <= 1)
);

CREATE INDEX idx_{schema}_processed_items_source_id ON {schema}.processed_items (source_id);
CREATE INDEX idx_{schema}_processed_items_processed_at ON {schema}.processed_items (processed_at);
CREATE INDEX idx_{schema}_processed_items_relevance_score ON {schema}.processed_items (relevance_score);
CREATE INDEX idx_{schema}_processed_items_published_at ON {schema}.processed_items (published_at);
CREATE INDEX idx_{schema}_processed_items_topics ON {schema}.processed_items USING GIN (topics);
CREATE INDEX idx_{schema}_processed_items_entities ON {schema}.processed_items USING GIN (entities);
```

`{schema}` yerine `news`, `market`, `geo`, `transport`, `fmcg` gelir. Migration bu 5 tabloyu döngüyle oluşturur.

### 4.5 content_chunks

```sql
CREATE TABLE content_chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processed_item_id   UUID NOT NULL,
    chunk_index         INTEGER NOT NULL,
    chunk_text          TEXT NOT NULL,
    token_count         INTEGER NOT NULL,
    embedding           VECTOR(1536) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_content_chunks_processed_item_id_chunk_index UNIQUE (processed_item_id, chunk_index)
);

CREATE INDEX idx_content_chunks_processed_item_id ON content_chunks (processed_item_id);
```

**FK notu:** `processed_item_id` mantıksal olarak processed_items'a referans verir ancak processed_items 5 ayrı schema'da olduğundan PostgreSQL native FK constraint uygulanamaz. Referential integrity uygulama katmanında (SQLAlchemy relationship) sağlanır.

**pgvector index:** Aşağıda §10'da detaylandırılmıştır.

**Embedding boyutu notu:** `VECTOR(1536)` OpenAI text-embedding-3-small için tanımlanır. Cohere embed-v3'e geçildiğinde boyut 1024 olur; bu durumda kolon ALTER ile güncellenir ve reindex job çalıştırılır.

### 4.6 digests

```sql
CREATE TABLE digests (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    digest_type           digest_type_enum NOT NULL,
    title                 VARCHAR(500) NOT NULL,
    status                digest_status_enum NOT NULL DEFAULT 'generating',
    period_start          DATE NOT NULL,
    period_end            DATE NOT NULL,
    s3_archive_key        VARCHAR(1024),
    total_sources_used    INTEGER NOT NULL DEFAULT 0,
    generation_metadata   JSONB DEFAULT '{}'::jsonb,
    error_message         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at          TIMESTAMPTZ
);

CREATE INDEX idx_digests_digest_type ON digests (digest_type);
CREATE INDEX idx_digests_status ON digests (status);
CREATE INDEX idx_digests_created_at ON digests (created_at DESC);
CREATE INDEX idx_digests_period ON digests (period_start, period_end);
```

### 4.7 digest_sections

```sql
CREATE TABLE digest_sections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    digest_id           UUID NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    section_order       INTEGER NOT NULL,
    section_title       VARCHAR(500) NOT NULL,
    ai_summary          TEXT NOT NULL,
    impact_note         TEXT,
    source_references   JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_template_id  UUID REFERENCES prompt_templates(id) ON DELETE SET NULL
);

CREATE INDEX idx_digest_sections_digest_id ON digest_sections (digest_id);
```

**ON DELETE davranışı:** Digest silindiğinde section'lar CASCADE ile silinir. Prompt template silindiğinde referans SET NULL olur (geçmiş section'lar korunur).

### 4.8 prompt_templates

```sql
CREATE TABLE prompt_templates (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                  VARCHAR(255) NOT NULL,
    digest_type           digest_type_enum NOT NULL,
    section_key           VARCHAR(100) NOT NULL,
    system_prompt         TEXT NOT NULL,
    user_prompt_template  TEXT NOT NULL,
    model_preference      VARCHAR(50),
    is_active             BOOLEAN NOT NULL DEFAULT true,
    version               INTEGER NOT NULL DEFAULT 1,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_prompt_templates_name UNIQUE (name)
);

CREATE INDEX idx_prompt_templates_digest_type ON prompt_templates (digest_type);
CREATE INDEX idx_prompt_templates_is_active ON prompt_templates (is_active);
```

### 4.9 api_keys

```sql
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        api_provider_enum NOT NULL,
    key_alias       VARCHAR(100) NOT NULL,
    encrypted_key   TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    priority_order  INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_api_keys_provider ON api_keys (provider);
CREATE INDEX idx_api_keys_is_active ON api_keys (is_active);
```

### 4.10 api_usage_logs

```sql
CREATE TABLE api_usage_logs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id        UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    provider          VARCHAR(50) NOT NULL,
    model             VARCHAR(100) NOT NULL,
    prompt_tokens     INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens      INTEGER NOT NULL,
    request_type      VARCHAR(50) NOT NULL,
    http_status       INTEGER NOT NULL,
    latency_ms        INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_api_usage_logs_api_key_id ON api_usage_logs (api_key_id);
CREATE INDEX idx_api_usage_logs_created_at ON api_usage_logs (created_at DESC);
CREATE INDEX idx_api_usage_logs_provider ON api_usage_logs (provider);
CREATE INDEX idx_api_usage_logs_request_type ON api_usage_logs (request_type);
```

Bu tablo yüksek yazma hacmine sahiptir (her LLM çağrısında bir kayıt). Admin panelindeki token kullanım grafikleri bu tablodan üretilir; `created_at DESC` index zaman bazlı sorguları hızlandırır.

### 4.11 chat_history

```sql
CREATE TABLE chat_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    sources     JSONB NOT NULL DEFAULT '[]'::jsonb,
    tokens_used INTEGER NOT NULL,
    model       VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_history_user_id ON chat_history (user_id);
CREATE INDEX idx_chat_history_created_at ON chat_history (created_at DESC);
```

**sources JSONB yapısı:**
```json
[
  {
    "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
    "processed_item_id": "660e8400-e29b-41d4-a716-446655440001",
    "score": 0.87,
    "title": "Haber başlığı"
  }
]
```

### 4.12 audit_logs

```sql
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      VARCHAR(100) NOT NULL,
    actor_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    target_type     VARCHAR(100),
    target_id       UUID,
    payload         JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_event_type ON audit_logs (event_type);
CREATE INDEX idx_audit_logs_actor_user_id ON audit_logs (actor_user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX idx_audit_logs_target ON audit_logs (target_type, target_id);
```

**ON DELETE davranışı:** Kullanıcı silindiğinde `actor_user_id` SET NULL olur — audit kaydı korunur, aktör bilgisi kaybolur.

**event_type değerleri:** `user.login`, `user.logout`, `user.created`, `user.deleted`, `user.role_changed`, `user.deactivated`, `source.created`, `source.deleted`, `source.status_changed`, `prompt_template.updated`, `api_key.created`, `api_key.deleted`, `digest.started`, `digest.completed`, `digest.failed`, `system.error`, `password.reset_initiated`, `password.reset_completed`.

### 4.13 notification_preferences

```sql
CREATE TABLE notification_preferences (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_enabled  BOOLEAN NOT NULL DEFAULT true,
    push_enabled   BOOLEAN NOT NULL DEFAULT true,
    fcm_token      TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_notification_preferences_user_id UNIQUE (user_id)
);
```

Her kullanıcı için en fazla bir kayıt (1:1). Kullanıcı oluşturulduğunda varsayılan tercihlerle otomatik oluşturulur.

### 4.14 password_reset_tokens

```sql
CREATE TABLE password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_password_reset_tokens_token_hash UNIQUE (token_hash)
);

CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens (user_id);
CREATE INDEX idx_password_reset_tokens_expires_at ON password_reset_tokens (expires_at);
```

Token doğrulama sorgusu: `WHERE token_hash = $1 AND expires_at > now() AND used_at IS NULL`.

### 4.15 system_settings

```sql
CREATE TABLE system_settings (
    key          VARCHAR(100) PRIMARY KEY,
    value        JSONB NOT NULL,
    description  TEXT,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   UUID REFERENCES users(id) ON DELETE SET NULL
);
```

Bu tablo UUID PK kullanmaz; `key` alanı doğal primary key'dir.

**Öntanımlı seed verisi:**

| key | value | description |
|-----|-------|-------------|
| `jwt_access_token_minutes` | `60` | Access token geçerlilik süresi (dk) |
| `jwt_refresh_token_days` | `30` | Refresh token geçerlilik süresi (gün) |
| `digest_schedule_strategy_weekly` | `"0 8 * * 5"` | Strateji bülteni cron (Cuma 08:00 UTC) |
| `digest_schedule_turkish_media_weekly` | `"0 8 * * 6"` | Türk Medyası bülteni cron (Cumartesi 08:00 UTC) |
| `digest_schedule_fmcg_weekly` | `"0 10 * * 6"` | FMCG bülteni cron (Cumartesi 10:00 UTC) |
| `embedding_model` | `"openai/text-embedding-3-small"` | Aktif embedding modeli |
| `embedding_chunk_size` | `512` | Chunk boyutu (token) |
| `embedding_chunk_overlap` | `64` | Chunk overlap (token) |

### 4.16 alarms (MVP-1)

```sql
CREATE TABLE alarms (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    rule_type   VARCHAR(100) NOT NULL,
    rule_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_by  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alarms_is_active ON alarms (is_active);
CREATE INDEX idx_alarms_rule_type ON alarms (rule_type);
```

Migration dosyası MVP-1 branch'inde oluşturulur; MVP-0'da bu tablo yoktur.

### 4.17 alarm_events (MVP-1)

```sql
CREATE TABLE alarm_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alarm_id      UUID NOT NULL REFERENCES alarms(id) ON DELETE CASCADE,
    trigger_data  JSONB NOT NULL DEFAULT '{}'::jsonb,
    notified      BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alarm_events_alarm_id ON alarm_events (alarm_id);
CREATE INDEX idx_alarm_events_created_at ON alarm_events (created_at DESC);
CREATE INDEX idx_alarm_events_notified ON alarm_events (notified);
```

---

## 5. Index Stratejisi

### B-tree Index'ler (Varsayılan)

Tüm FK kolonları, `created_at` (DESC), `status`/`is_active` filtreleme kolonları ve sık sorgulanan alanlar B-tree index alır. Yukarıdaki tablo tanımlarında her index açıkça belirtilmiştir.

### GIN Index'ler (JSONB)

`processed_items.topics` ve `processed_items.entities` JSONB dizileri üzerinde GIN index uygulanır. Bu index `@>` (contains) operatörü ile konu/entity bazlı filtrelemeyi hızlandırır.

Örnek sorgu:
```sql
SELECT * FROM news.processed_items
WHERE topics @> '["gıda fiyatları"]'::jsonb
AND processed_at > now() - INTERVAL '7 days';
```

### pgvector Index'ler

`content_chunks.embedding` kolonu üzerinde HNSW index uygulanır. Detaylar §10'da.

### Composite Index'ler

| Tablo | Index | Kolonlar | Amaç |
|-------|-------|----------|------|
| `raw_items` | `uq_raw_items_source_id_content_hash` | `(source_id, content_hash)` | Dedup UNIQUE constraint |
| `content_chunks` | `uq_content_chunks_processed_item_id_chunk_index` | `(processed_item_id, chunk_index)` | Chunk sıra UNIQUE |
| `audit_logs` | `idx_audit_logs_target` | `(target_type, target_id)` | Hedef entity bazlı log sorgusu |
| `digests` | `idx_digests_period` | `(period_start, period_end)` | Dönem bazlı digest sorgusu |

### Index Ekleme Kuralı

Yeni bir endpoint veya sorgu pattern'i eklendiğinde EXPLAIN ANALYZE ile sorgu planı kontrol edilir. Sequential scan > 1000 satır dönen sorgulara index eklenir. Index ekleme migration dosyası gerektirir.

---

## 6. ERD (SQL-Seviye)

```mermaid
erDiagram
    users ||--o{ chat_history : "user_id"
    users ||--o| notification_preferences : "user_id"
    users ||--o{ audit_logs : "actor_user_id"
    users ||--o{ password_reset_tokens : "user_id"
    users ||--o{ alarms : "created_by"
    users ||--o{ system_settings : "updated_by"

    sources ||--o{ raw_items : "source_id"

    raw_items ||--o| news_processed_items : "raw_item_id"
    raw_items ||--o| market_processed_items : "raw_item_id"
    raw_items ||--o| geo_processed_items : "raw_item_id"
    raw_items ||--o| transport_processed_items : "raw_item_id"
    raw_items ||--o| fmcg_processed_items : "raw_item_id"

    news_processed_items ||--o{ content_chunks : "processed_item_id"
    market_processed_items ||--o{ content_chunks : "processed_item_id"
    geo_processed_items ||--o{ content_chunks : "processed_item_id"
    transport_processed_items ||--o{ content_chunks : "processed_item_id"
    fmcg_processed_items ||--o{ content_chunks : "processed_item_id"

    digests ||--o{ digest_sections : "digest_id"
    digest_sections }o--o| prompt_templates : "prompt_template_id"

    api_keys ||--o{ api_usage_logs : "api_key_id"

    alarms ||--o{ alarm_events : "alarm_id"

    users {
        uuid id PK
        varchar email UK
        varchar password_hash
        varchar full_name
        user_role_enum role
        boolean is_active
    }

    sources {
        uuid id PK
        varchar name
        source_type_enum source_type
        jsonb config
        source_status_enum status
        integer error_count
        source_category_enum category
    }

    raw_items {
        uuid id PK
        uuid source_id FK
        varchar content_hash
        raw_item_status_enum status
        text raw_content
    }

    news_processed_items {
        uuid id PK
        uuid raw_item_id FK-UK
        uuid source_id FK
        float relevance_score
        jsonb topics
        jsonb entities
    }

    content_chunks {
        uuid id PK
        uuid processed_item_id FK
        integer chunk_index
        vector_1536 embedding
        integer token_count
    }

    digests {
        uuid id PK
        digest_type_enum digest_type
        digest_status_enum status
        date period_start
        date period_end
    }

    digest_sections {
        uuid id PK
        uuid digest_id FK
        integer section_order
        text ai_summary
        text impact_note
        uuid prompt_template_id FK
    }

    prompt_templates {
        uuid id PK
        varchar name UK
        digest_type_enum digest_type
        varchar section_key
        integer version
    }

    api_keys {
        uuid id PK
        api_provider_enum provider
        varchar key_alias
        text encrypted_key
        integer priority_order
    }

    api_usage_logs {
        uuid id PK
        uuid api_key_id FK
        varchar model
        integer total_tokens
        varchar request_type
    }

    chat_history {
        uuid id PK
        uuid user_id FK
        text question
        text answer
        jsonb sources
    }

    audit_logs {
        uuid id PK
        varchar event_type
        uuid actor_user_id FK
        jsonb payload
    }

    notification_preferences {
        uuid id PK
        uuid user_id FK-UK
        boolean email_enabled
        boolean push_enabled
    }

    password_reset_tokens {
        uuid id PK
        uuid user_id FK
        varchar token_hash UK
        timestamptz expires_at
    }

    system_settings {
        varchar key PK
        jsonb value
        uuid updated_by FK
    }

    alarms {
        uuid id PK
        varchar name
        varchar rule_type
        jsonb rule_config
        uuid created_by FK
    }

    alarm_events {
        uuid id PK
        uuid alarm_id FK
        jsonb trigger_data
        boolean notified
    }
```

Diyagramda `news_processed_items` diğer 4 schema tablosunu temsil eder (`market_processed_items`, `geo_processed_items`, `transport_processed_items`, `fmcg_processed_items`). Hepsi aynı yapıya sahiptir.

---

## 7. Migration Stratejisi

### Araç

Alembic (SQLAlchemy migration tool) kullanılır. Konfigürasyon: `alembic.ini` + `alembic/env.py`.

### Migration Dosya Yapısı

```
/packages/shared/alembic/
  env.py
  versions/
    001_initial_schema.py
    002_create_enum_types.py
    003_create_users_table.py
    004_create_sources_table.py
    ...
```

### Versiyon Numaralandırma

Migration dosyaları `NNN_kısa_açıklama.py` formatında adlandırılır. Sıralı numara (001, 002, ...) kullanılır. Alembic revision ID otomatik üretilir.

### Dev vs Prod Akışı

| Adım | Dev Ortamı | Prod Ortamı |
|------|-----------|-------------|
| Migration oluşturma | `alembic revision --autogenerate -m "açıklama"` | Aynı dosya kullanılır |
| Migration çalıştırma | `alembic upgrade head` (otomatik, her deploy'da) | `alembic upgrade head` (manuel onay sonrası) |
| Rollback | `alembic downgrade -1` (geliştirici kararıyla) | Yasak — sadece ileri migration. Hata durumunda yeni düzeltme migration'ı yazılır |
| Onay | Gerekmez | Zorunlu — admin/DevOps onayı olmadan production migration çalıştırılamaz |

### Migration Kuralları

- Her migration dosyası hem `upgrade()` hem `downgrade()` fonksiyonunu içerir.
- Production ortamında `downgrade()` çalıştırılmaz. Rollback gerekiyorsa yeni bir düzeltme migration'ı yazılır.
- Migration dosyasında raw SQL yerine Alembic `op.*` fonksiyonları kullanılır. Tek istisna: pgvector extension yükleme (`op.execute("CREATE EXTENSION IF NOT EXISTS vector")`) ve enum type oluşturma.
- Her yeni tablo için migration dosyası zorunludur. Agent (Cursor/Claude Code) migration'ı production ortamında onaysız çalıştıramaz.
- Migration dosyası PR'ın parçasıdır; kod review kapsamında incelenir.

### İlk Migration Sırası (MVP-0)

1. pgvector extension yükleme + schema oluşturma
2. Enum type'lar
3. `users`
4. `sources`
5. `raw_items`
6. `processed_items` (5 schema'da)
7. `content_chunks`
8. `digests`
9. `digest_sections`
10. `prompt_templates`
11. `api_keys`
12. `api_usage_logs`
13. `chat_history`
14. `audit_logs`
15. `notification_preferences`
16. `password_reset_tokens`
17. `system_settings` + seed data
18. pgvector HNSW index

---

## 8. Seed Data

### Dev Ortamı

Dev ortamında `fixtures/` klasöründe JSON seed dosyaları kullanılır. Production verisi dev ortamına taşınamaz.

Seed dosyaları:

| Dosya | İçerik |
|-------|--------|
| `fixtures/users.json` | 1 admin + 2 viewer test kullanıcısı |
| `fixtures/sources.json` | 5 RSS + 2 email + 1 gov kaynak (gerçek URL'ler, test amaçlı) |
| `fixtures/prompt_templates.json` | Her bülten tipi için 2-3 örnek template |
| `fixtures/system_settings.json` | Tüm varsayılan sistem ayarları |
| `fixtures/raw_items.json` | 50 örnek ham veri (RSS çıktısı simülasyonu) |
| `fixtures/processed_items.json` | 50 örnek işlenmiş veri (5 schema'ya dağıtılmış) |

Seed yükleme komutu: `python -m scripts.seed_dev` — bu komut yalnızca `dev` ortamında çalışır; `prod` ortamında çalıştırılırsa hata verir.

### Production Ortamı

İlk production deploy'unda yalnızca şu seed verisi yüklenir:

1. **İlk admin kullanıcı:** E-posta ve şifre deploy sırasında environment variable'dan okunur (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`). Bu değerler seed sonrası env'den silinir.
2. **System settings:** Varsayılan değerler (JWT süreleri, cron ifadeleri, embedding ayarları).
3. **Sources:** Admin panelinden manuel eklenir; seed ile yüklenmez.

---

## 9. Retention ve Arşivleme

| Tablo | Aktif Retention | Arşiv Hedefi | Arşiv Mekanizması |
|-------|----------------|-------------|-------------------|
| `audit_logs` | 90 gün | S3 (`s3://{env}-ygip-archive/audit-logs/{YYYY}/{MM}/`) | Scheduled Lambda job, aylık |
| `raw_items` | 180 gün | S3 (`s3://{env}-ygip-archive/raw-items/{YYYY}/{MM}/`) | Scheduled Lambda job, aylık |
| `api_usage_logs` | 365 gün | S3 (`s3://{env}-ygip-archive/api-usage/{YYYY}/{MM}/`) | Scheduled Lambda job, aylık |
| `processed_items` | Süresiz (aktif tabloda) | — | Arşivlenmez; digest üretimi için gerekli |
| `content_chunks` | Süresiz (aktif tabloda) | — | Arşivlenmez; RAG sorguları için gerekli |
| `chat_history` | Süresiz (aktif tabloda) | — | Arşivlenmez; admin görüntülemesi için gerekli |
| `digests` + `digest_sections` | Süresiz (aktif tabloda) | — | Arşivlenmez; kullanıcılar geçmiş bültenlere erişir |

Arşivleme süreci:
1. Lambda job retention süresini aşan kayıtları JSON formatında S3'e yazar.
2. S3'e yazma başarılı olduktan sonra kaynak tablodaki kayıtlar silinir.
3. Silme işlemi batch halinde (1000 kayıt/batch) yapılır; tablo kilitlenmesini önler.
4. İşlem sonucu audit_logs'a yazılır.

---

## 10. pgvector Kurulum ve Yapılandırma

### Extension Yükleme

İlk migration'ın ilk adımı:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Bu komut Alembic migration dosyasında `op.execute()` ile çalıştırılır.

### VECTOR Kolon Tipi

`content_chunks.embedding` kolonu `VECTOR(1536)` olarak tanımlanır (OpenAI text-embedding-3-small boyutu). Cohere embed-v3'e geçildiğinde:

```sql
ALTER TABLE content_chunks ALTER COLUMN embedding TYPE VECTOR(1024);
```

Bu değişiklik migration dosyası gerektirir ve ardından reindex job çalıştırılır.

### Similarity Search

Cosine similarity kullanılır. pgvector `<=>` operatörü cosine distance döner (1 - cosine_similarity).

Örnek sorgu (uygulama katmanında SQLAlchemy ile):

```python
from sqlalchemy import select, func

stmt = (
    select(ContentChunk)
    .order_by(ContentChunk.embedding.cosine_distance(query_embedding))
    .limit(10)
)
```

RAG chatbot'ta kullanılan sorgu pattern'i: kullanıcı sorusu embedding'e dönüştürülür → `content_chunks` tablosunda cosine similarity ile en yakın top-K chunk seçilir → seçilen chunk'lar LLM'e context olarak verilir.

### HNSW Index

```sql
CREATE INDEX idx_content_chunks_embedding_hnsw
ON content_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

HNSW parametreleri:
- `m = 16`: Her node'un bağlantı sayısı. Varsayılan ve orta ölçekli veri setleri için uygun.
- `ef_construction = 64`: Index oluşturma kalitesi. Yüksek değer daha iyi recall ama daha yavaş index oluşturma.

HNSW, IVFFlat'e göre tercih edilir çünkü: daha iyi recall-performance dengesi sunar, incremental insert destekler (IVFFlat'te her insert sonrası reindex gerekmez), ve MVP-0 veri hacminde (<100K chunk) her iki yöntem de yeterli performans verir.

### Reindex Job

Embedding modeli değiştiğinde veya VECTOR boyutu güncellendiğinde reindex job çalıştırılır:

1. `system_settings` tablosundan yeni model okunur.
2. Tüm `content_chunks` kayıtları batch halinde (500 chunk/batch) okunur.
3. Her batch için yeni model ile embedding üretilir.
4. Üretilen embedding'ler `content_chunks.embedding` kolonuna yazılır.
5. HNSW index otomatik güncellenir (incremental).
6. İşlem tamamlandığında audit_logs'a kayıt yazılır.

Reindex job background task olarak çalışır; chatbot sorguları reindex sırasında da çalışmaya devam eder (mevcut index kullanılır, güncellenen satırlar anında index'e dahil olur).

---

## 11. Backup Stratejisi

| Ortam | Backup | PITR | Retention | Snapshot Frekansı |
|-------|--------|------|-----------|-------------------|
| `prod` | Aktif | Aktif (5 dk granularity) | 7 gün | Otomatik günlük |
| `dev` | Kapalı | Kapalı | — | — |

AWS RDS ayarları:
- `BackupRetentionPeriod`: 7 (prod), 0 (dev)
- `PreferredBackupWindow`: `03:00-04:00` UTC (Türkiye saati 06:00-07:00, düşük kullanım saati)
- `DeletionProtection`: `true` (prod), `false` (dev)
- `MultiAZ`: `false` (MVP-0 — tek AZ yeterli, ~30 kullanıcı); MVP-1'de değerlendirilir

Geri yükleme senaryosunda RDS PITR ile belirli bir zamana dönülebilir. Tam geri yükleme en son snapshot'tan yapılır. Her iki durumda da DevOps onayı gereklidir.

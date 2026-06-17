# 08 — Test Stratejisi

> **Platform:** YıldızHolding Global Intelligence Platform (YGIP)
> **Kapsam:** Test piramidi, coverage hedefleri, fixture stratejisi, mock politikası, CI/CD entegrasyonu, kritik test senaryoları — MVP-0 implementasyon detayı

---

## 1. Test Felsefesi ve Hedefleri

YGIP düşük kullanıcılı (~30 kişi) dahili bir platformdur. Belirleyici yük kullanıcı trafiği değil, veri toplama pipeline'ının işlem hacmidir. Test stratejisi bu profile göre şekillenir:

**Risk-bazlı önceliklendirme:** Her modül eşit coverage hedefi taşımaz. Veri bütünlüğünü etkileyen katmanlar (dedup, normalize, score, digest üretim) yüksek coverage hedefler; UI bileşenleri ve statik sayfa render'ları düşük önceliklidir.

**Coverage hedefleri:**

| Katman | Hedef | Gerekçe |
|--------|-------|---------|
| Collector veri çekimi | %70+ | Dış kaynak parse hataları en sık failure noktası |
| Processor pipeline (dedup, normalize, enrich, score) | %80+ | Veri bütünlüğü kritik — yanlış skor veya kayıp makale digest kalitesini doğrudan etkiler |
| AI engine (prompt render, çıktı parse, LLM client) | %70+ | LLM çıktı formatı değişkenlik gösterir; parse logic sağlam olmalı |
| Auth ve RBAC | %90+ | Güvenlik kritik — bypass senaryoları kesinlikle test edilmeli |
| API router'lar | %60+ | Pydantic validation + guard testi yeterli; iş mantığı servis katmanında |
| Repository (DB erişim) | %50+ | ORM sorguları basit CRUD; karmaşık sorgular (similarity search, aggregation) test edilir |

**Genel kural:** Kritik iş mantığı %70+ coverage hedefler. Bu hedef CI gate olarak uygulanır — PR'da coverage düşerse merge engellenir.

---

## 2. Test Piramidi

```
        ╱  E2E  ╲          → MVP-0'da kapsam dışı
       ╱──────────╲
      ╱ Integration ╲      → DB, API endpoint, SQS akışı, pgvector
     ╱────────────────╲
    ╱    Unit Tests     ╲   → İş mantığı, parse, hash, validation, guard
   ╱──────────────────────╲
```

| Katman | Kapsam | Oran | Araçlar |
|--------|--------|------|---------|
| **Unit** | Tek fonksiyon/class, dış bağımlılık yok | ~%70 | pytest, pytest-asyncio, unittest.mock |
| **Integration** | DB + API + Redis + SQS birlikte | ~%25 | pytest, httpx.AsyncClient, testcontainers, moto |
| **E2E** | Tarayıcı/mobil üzerinden uçtan uca akış | ~%5 | MVP-0'da yok, MVP-1'de Playwright değerlendirilir |

Unit ve integration test MVP-0'dan itibaren zorunludur. E2E test MVP-1'de dashboard olgunlaştığında eklenir.

---

## 3. Unit Test Stratejisi

Unit testler tek bir fonksiyon veya class'ı izole ederek test eder. Dış bağımlılıklar (DB, Redis, HTTP, LLM API) mock'lanır.

### 3.1 Collector Testleri

Her collector tipi için mock kaynak verisi ile `collect()` çıktısı doğrulanır:

```python
# tests/unit/collectors/test_rss_collector.py
import pytest
from unittest.mock import AsyncMock, patch
from services.collectors.rss_collector import RSSCollector

@pytest.fixture
def sample_rss_xml():
    return open("fixtures/rss/sample_feed.xml").read()

@pytest.mark.asyncio
async def test_rss_collector_parses_valid_feed(sample_rss_xml):
    collector = RSSCollector()
    with patch.object(collector, "_fetch", return_value=sample_rss_xml):
        source = make_source(source_type="rss", config={"feed_url": "https://example.com/feed"})
        articles = await collector.collect(source)
        assert len(articles) > 0
        assert all(a.title for a in articles)
        assert all(a.content for a in articles)

@pytest.mark.asyncio
async def test_rss_collector_handles_malformed_xml():
    collector = RSSCollector()
    with patch.object(collector, "_fetch", return_value="<not>valid</xml>"):
        source = make_source(source_type="rss")
        articles = await collector.collect(source)
        assert articles == []
```

Test edilecek collector senaryoları:

| Collector | Başarılı Parse | Hatalı Girdi | Boş Yanıt | Encoding Sorunu |
|-----------|:-----------:|:----------:|:--------:|:--------------:|
| RSS | ✅ | ✅ | ✅ | ✅ (UTF-8, ISO-8859-9) |
| Email (IMAP) | ✅ | ✅ | ✅ | ✅ (HTML body, plain text) |
| Gov | ✅ | ✅ | ✅ | ✅ (Türkçe karakter) |
| REST API (MVP-1) | ✅ | ✅ | ✅ | — |

### 3.2 Processor Pipeline Testleri

Her pipeline adımı bağımsız test edilir:

**Dedup:**
```python
@pytest.mark.asyncio
async def test_dedup_detects_duplicate_hash():
    dedup = DedupProcessor(redis=FakeRedis())
    await dedup.mark_seen("sha256:abc123")
    assert await dedup.is_duplicate("sha256:abc123") is True

@pytest.mark.asyncio
async def test_dedup_allows_new_hash():
    dedup = DedupProcessor(redis=FakeRedis())
    assert await dedup.is_duplicate("sha256:new_hash") is False
```

**Normalize:**
- HTML tag temizleme: `<p>Metin</p>` → `Metin`
- Unicode normalizasyon: NFC dönüşümü
- Whitespace düzenleme: çoklu boşluk → tek boşluk
- Türkçe karakter koruması: `ışığın` bozulmamalı

**Gate:**
- `ingest_mode: "all"` → keyword araması olmadan geçer
- `ingest_mode: "filtered"` + master havuzda eşleşme → geçer
- `ingest_mode: "filtered"` + eşleşme yok → DROP (`processed_items` yazılmaz)

**Score:**
- Deterministik formül: `keyword_intensity * 0.6 + freshness * 0.4`
- Edge case: `relevance_score` her zaman 0.0–1.0 aralığında
- Source reliability weight yok (K3 kararı)

### 3.3 AI Engine Testleri

LLM API çağrıları unit testlerde mock'lanır. Gerçek API çağrısı yapılmaz.

**Prompt rendering:**
```python
def test_prompt_template_renders_articles():
    renderer = PromptRenderer()
    template = PromptTemplate(
        system_prompt="Sen bir analistsin.",
        user_prompt_template="Şu haberleri özetle: {{ articles }}",
    )
    result = renderer.render(template, articles=[{"title": "Test", "content": "İçerik"}])
    assert "Test" in result
    assert "İçerik" in result
```

**LLM çıktı parse:**
- Geçerli JSON çıktı → başarılı parse
- Geçersiz JSON (LLM hallucination) → parse hatası, fallback
- Eksik alan (summary yok) → varsayılan değer veya hata

**Round-robin fallback:**
```python
@pytest.mark.asyncio
async def test_llm_client_falls_back_on_rate_limit():
    provider_a = MockProvider(raises=RateLimitError)
    provider_b = MockProvider(returns="Yanıt")
    client = LLMClient(providers=[provider_a, provider_b])
    response = await client.complete("test prompt")
    assert response.text == "Yanıt"
    assert provider_b.call_count == 1
```

### 3.4 Auth ve Güvenlik Testleri

**JWT:**
- Geçerli token → doğru payload decode
- Expired token → `UnauthorizedException`
- Tampered token → `UnauthorizedException`
- Yanlış algorithm → `UnauthorizedException`

**Şifre:**
- bcrypt hash üretimi ve doğrulama
- Şifre politikası (min 8 karakter, 1 büyük harf, 1 rakam): geçerli ve geçersiz örnekler

**Guard:**
```python
def test_require_admin_rejects_viewer():
    viewer = make_user(role=UserRole.VIEWER)
    with pytest.raises(ForbiddenException):
        require_admin(current_user=viewer)

def test_require_admin_allows_admin():
    admin = make_user(role=UserRole.ADMIN)
    result = require_admin(current_user=admin)
    assert result == admin
```

### 3.5 Pydantic Schema Testleri

Request ve response schema'larının doğrulama kuralları test edilir:

```python
def test_create_user_request_rejects_short_password():
    with pytest.raises(ValidationError):
        CreateUserRequest(email="test@test.com", full_name="Test", password="123")

def test_create_user_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        CreateUserRequest(email="not-an-email", full_name="Test", password="ValidPass1")
```

---

## 4. Integration Test Stratejisi

Integration testler gerçek bağımlılıklarla (DB, Redis, API) birlikte çalışır. Dış servisler (LLM API, SMTP, FCM, dış RSS kaynakları) mock'lanır.

### 4.1 Veritabanı Testleri

PostgreSQL + pgvector test ortamı testcontainers ile sağlanır:

```python
# tests/conftest.py
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

@pytest_asyncio.fixture(scope="session")
async def db_container():
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        yield pg.get_connection_url()

@pytest_asyncio.fixture
async def db_session(db_container):
    engine = create_async_engine(db_container)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()
```

Her test fonksiyonu temiz bir transaction içinde çalışır ve sonunda rollback yapılır — testler birbirini etkilemez.

Test edilecek DB senaryoları:
- CRUD operasyonları (user, source, digest, chat_history)
- Unique constraint ihlali (`uq_users_email`, `uq_raw_items_source_id_content_hash`)
- CASCADE silme (source silindiğinde raw_items silinir)
- pgvector similarity search (embedding insert → cosine distance sorgu → doğru sıralama)
- Schema-partitioned processed_items yazma (`news.processed_items`, `market.processed_items`)

### 4.2 API Endpoint Testleri

FastAPI TestClient (httpx.AsyncClient) ile endpoint testleri:

```python
@pytest.mark.asyncio
async def test_login_success(client, seed_admin_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "AdminPass1",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

@pytest.mark.asyncio
async def test_viewer_cannot_create_user(client, viewer_token):
    response = await client.post(
        "/api/v1/users",
        json={"email": "new@test.com", "full_name": "New", "password": "NewPass1"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403
```

Her endpoint grubu için test edilecek senaryolar:

| Endpoint | Başarılı | Yetkisiz (401) | Yasak (403) | Validation (422) | Conflict (409) |
|----------|:-------:|:-------------:|:-----------:|:----------------:|:-------------:|
| Auth login | ✅ | ✅ (yanlış şifre) | — | ✅ (eksik alan) | — |
| Auth refresh | ✅ | ✅ (expired token) | — | — | — |
| User CRUD | ✅ | ✅ | ✅ (viewer) | ✅ | ✅ (duplicate email) |
| Source CRUD | ✅ | ✅ | ✅ (viewer) | ✅ | — |
| Digest list/detail | ✅ | ✅ | — | — | — |
| Digest trigger | ✅ | ✅ | ✅ (viewer) | — | — |
| Chatbot ask | ✅ | ✅ | — | ✅ (boş soru) | — |
| Audit logs | ✅ | ✅ | ✅ (viewer) | — | — |

### 4.3 SQS Mesaj Akışı Testleri

AWS servislerinin mock'u moto kütüphanesi ile yapılır:

```python
@pytest.mark.asyncio
async def test_collector_sends_to_sqs(moto_sqs):
    collector = RSSCollector()
    # ... collect + transform
    await send_to_sqs(normalized_article, "rss")
    messages = moto_sqs.receive_messages("ygip-test-rss-queue")
    assert len(messages) == 1
    body = json.loads(messages[0]["Body"])
    assert body["source_type"] == "rss"
```

### 4.4 Redis Integration Testleri

Rate limiting ve dedup testleri fakeredis ile yapılır:

```python
@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit(fake_redis):
    limiter = RateLimiter(redis=fake_redis, limit=10, window=60)
    for _ in range(10):
        assert await limiter.check("test-key") is True
    assert await limiter.check("test-key") is False  # 11. istek blocked
```

---

## 5. Fixture ve Seed Stratejisi

### 5.1 JSON Fixture Dosyaları

`fixtures/` klasöründe dev ortamı ve test ortamı için kullanılan seed dosyaları bulunur:

| Dosya | İçerik | Kullanım |
|-------|--------|---------|
| `fixtures/users.json` | 1 admin + 2 viewer test kullanıcısı | Dev seed + test |
| `fixtures/sources.json` | 5 RSS + 2 email + 1 gov kaynak | Dev seed + test |
| `fixtures/prompt_templates.json` | Her bülten tipi için 2-3 şablon | Dev seed + test |
| `fixtures/system_settings.json` | Tüm varsayılan sistem ayarları | Dev seed + test |
| `fixtures/raw_items.json` | 50 örnek ham veri | Dev seed |
| `fixtures/processed_items.json` | 50 örnek işlenmiş veri (5 schema) | Dev seed |
| `fixtures/rss/sample_feed.xml` | Geçerli RSS feed XML'i | Unit test |
| `fixtures/rss/malformed_feed.xml` | Bozuk RSS XML'i | Unit test |
| `fixtures/email/sample_newsletter.eml` | Örnek newsletter e-postası | Unit test |
| `fixtures/llm/digest_response.json` | Örnek LLM digest çıktısı | Unit test |
| `fixtures/llm/chatbot_response.json` | Örnek LLM chatbot çıktısı | Unit test |

Production verisi dev ortamına taşınamaz. Fixture verisi gerçek URL'ler ve yapılandırmalar içerir ancak API key veya credential içermez.

### 5.2 Factory Pattern

Testlerde tekrarlayan entity oluşturma işlemleri factory fonksiyonları ile standartlaştırılır:

```python
# tests/factories/user_factory.py
from packages.shared.models.user import User
from packages.shared.enums.user_role import UserRole

def make_user(
    email: str = "test@test.com",
    full_name: str = "Test User",
    role: UserRole = UserRole.VIEWER,
    is_active: bool = True,
    password_hash: str = "$2b$12$...",  # pre-computed hash for "TestPass1"
) -> User:
    return User(
        email=email,
        full_name=full_name,
        role=role,
        is_active=is_active,
        password_hash=password_hash,
    )
```

Her entity için factory: `make_user()`, `make_source()`, `make_raw_item()`, `make_processed_item()`, `make_digest()`, `make_prompt_template()`, `make_api_key()`, `make_audit_log()`.

Factory fonksiyonları `tests/factories/` altında tutulur ve `conftest.py`'den import edilir.

---

## 6. Mock ve Stub Politikası

| Bağımlılık | Unit Test | Integration Test | Gerekçe |
|-----------|:---------:|:---------------:|---------|
| PostgreSQL | Mock (in-memory) | Gerçek (testcontainers) | Integration testlerde gerçek SQL davranışı gerekli |
| Redis | fakeredis | fakeredis | Gerçek Redis gereksiz — fakeredis tüm komutları destekler |
| LLM API (Groq, Gemini) | Mock | Mock | Gerçek API çağrısı maliyetli ve nondeterministik |
| SMTP (mail) | Mock | Mock | Gerçek mail gönderimi test ortamında istenmeyen |
| AWS SQS | Mock | Mock (moto) | Gerçek SQS gereksiz — moto tam emülasyon sağlar |
| AWS S3 | Mock | Mock (moto) | Gerçek S3 gereksiz |
| FCM (push) | Mock | Mock | Gerçek push gönderimi test ortamında istenmeyen |
| Dış RSS/IMAP kaynakları | Mock (fixture XML/EML) | Mock | Dış kaynak güvenilirliğine bağımlılık yaratma |
| pgvector | — | Gerçek (testcontainers) | Similarity search doğrulaması gerçek extension gerektirir |

**Kural:** Test deterministik olmalıdır. Aynı girdi her zaman aynı çıktıyı üretir. Dış servis bağımlılığı olan test nondeterministiktir ve CI'da intermittent failure üretir — bu nedenle tüm dış servisler mock'lanır.

---

## 7. CI/CD Test Entegrasyonu

### 7.1 GitHub Actions Pipeline

Her PR açıldığında ve her commit push'unda otomatik çalışır:

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: ygip_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Lint
        run: ruff check .
      - name: Type check
        run: mypy apps/ services/ packages/
      - name: Unit tests
        run: pytest tests/unit -v --cov=apps --cov=services --cov=packages --cov-report=xml
      - name: Integration tests
        run: pytest tests/integration -v --cov-append --cov-report=xml
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/ygip_test
      - name: Coverage report
        run: coverage report --fail-under=70
```

### 7.2 Pipeline Aşamaları ve Gate'ler

| Aşama | Araç | Fail Koşulu | Süre Tahmini |
|-------|------|------------|-------------|
| Lint | ruff | Herhangi bir lint hatası | ~10 sn |
| Type check | mypy | Type error | ~30 sn |
| Unit test | pytest | Herhangi bir test fail | ~1-2 dk |
| Integration test | pytest + testcontainers | Herhangi bir test fail | ~2-3 dk |
| Coverage | coverage.py | Toplam coverage < %70 | ~5 sn |

Herhangi bir aşama fail olursa pipeline durur ve PR merge edilemez. Coverage raporu PR comment olarak eklenir — reviewer değişen dosyaların coverage'ını görebilir.

### 7.3 Agent Merge Kuralları

Agent (Cursor / Claude Code) kullanıcı onayı olmadan `main` branch'e merge edemez. Agent iş akışı:

1. Agent `feature/mvp-0` branch'inde çalışır.
2. Kod tamamlandığında PR açar.
3. CI pipeline tüm aşamalardan geçer.
4. İnsan reviewer kodu inceler.
5. Reviewer onaylarsa merge yapılır.

Agent'ın yapamayacağı işlemler:
- `main` branch'e doğrudan push
- CI fail olan PR'ı merge etme
- Coverage düşüren değişikliği onaysız merge etme
- Test olmadan yeni feature merge etme

---

## 8. Test Dosya Organizasyonu

```
/tests/
    conftest.py                          → Global fixture'lar (DB session, auth token, factory import)
    /factories/
        user_factory.py                  → make_user()
        source_factory.py                → make_source()
        article_factory.py               → make_raw_item(), make_processed_item()
        digest_factory.py                → make_digest(), make_digest_section()
        prompt_factory.py                → make_prompt_template()
        api_key_factory.py               → make_api_key()
        audit_factory.py                 → make_audit_log()
    /unit/
        conftest.py                      → Unit test-specific fixture'lar
        /collectors/
            test_rss_collector.py
            test_email_collector.py
            test_gov_collector.py
        /processor/
            test_dedup.py
            test_normalizer.py
            test_enricher.py
            test_scorer.py
            test_chunker.py
        /ai_engine/
            test_llm_client.py
            test_digest_generator.py
            test_rag_pipeline.py
            test_prompt_renderer.py
        /core/
            test_security.py             → JWT, bcrypt testleri
            test_pagination.py
        /schemas/
            test_auth_schemas.py
            test_user_schemas.py
            test_source_schemas.py
    /integration/
        conftest.py                      → DB session, API client, seed data
        test_auth_endpoints.py
        test_user_endpoints.py
        test_source_endpoints.py
        test_digest_endpoints.py
        test_chatbot_endpoints.py
        test_audit_endpoints.py
        test_settings_endpoints.py
        test_db_operations.py
        test_pgvector_search.py
        test_sqs_flow.py
```

### Naming Convention

- Test dosyası: `test_{module}.py`
- Test fonksiyonu: `test_{ne_test_ediliyor}` — açıklayıcı isim, `test_1`, `test_2` gibi numaralı isimler yasak
- Fixture: `{entity}_fixture` veya `make_{entity}()`
- conftest.py: Her dizinde bir tane, yalnızca o dizinin testlerine özel fixture'lar

### conftest.py Yapısı (Kök)

```python
# tests/conftest.py
import pytest_asyncio
from httpx import AsyncClient
from apps.api.main import app
from tests.factories.user_factory import make_user

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest_asyncio.fixture
async def admin_token(client, db_session):
    admin = make_user(role=UserRole.ADMIN, email="admin@test.com")
    db_session.add(admin)
    await db_session.flush()
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "AdminPass1"
    })
    return response.json()["access_token"]

@pytest_asyncio.fixture
async def viewer_token(client, db_session):
    viewer = make_user(role=UserRole.VIEWER, email="viewer@test.com")
    db_session.add(viewer)
    await db_session.flush()
    response = await client.post("/api/v1/auth/login", json={
        "email": "viewer@test.com", "password": "ViewerPass1"
    })
    return response.json()["access_token"]
```

---

## 9. Kritik Test Senaryoları

Aşağıdaki senaryolar kesinlikle test edilmelidir. Bu liste yeni feature eklendiğinde genişletilir.

### 9.1 Auth Akışı

| Senaryo | Beklenen Sonuç | Tip |
|---------|----------------|-----|
| Geçerli email + şifre ile login | 200, access + refresh token döner | Integration |
| Yanlış şifre ile login | 401, generic hata mesajı | Integration |
| Var olmayan email ile login | 401, generic hata mesajı (email varlığı açığa vurulmaz) | Integration |
| Pasif kullanıcı login | 401, generic hata mesajı | Integration |
| Geçerli refresh token ile yenileme | 200, yeni access + refresh token | Integration |
| Expired refresh token ile yenileme | 401, TOKEN_EXPIRED | Integration |
| Pasif kullanıcı refresh token ile yenileme | 401, USER_DEACTIVATED | Integration |
| Login rate limit aşımı (11. istek/dk) | 429, RATE_LIMIT_EXCEEDED | Integration |

### 9.2 RBAC Guard

| Senaryo | Beklenen Sonuç | Tip |
|---------|----------------|-----|
| Admin → `POST /users` | 200/201, kullanıcı oluşturulur | Integration |
| Viewer → `POST /users` | 403, FORBIDDEN | Integration |
| Admin → `GET /audit-logs` | 200, loglar döner | Integration |
| Viewer → `GET /audit-logs` | 403, FORBIDDEN | Integration |
| Admin → `POST /digests/trigger` | 200, digest tetiklenir | Integration |
| Viewer → `POST /digests/trigger` | 403, FORBIDDEN | Integration |
| Token'sız istek → korumalı endpoint | 401, UNAUTHORIZED | Integration |

### 9.3 Collector Retry ve Backoff

| Senaryo | Beklenen Sonuç | Tip |
|---------|----------------|-----|
| Kaynak 1. denemede başarılı | Veri SQS'e gönderilir, error_count sıfır | Unit |
| Kaynak 1. ve 2. deneme fail, 3. başarılı | Veri SQS'e gönderilir, backoff süreleri doğru | Unit |
| Kaynak 3 deneme fail | Hata loglanır, admin'e bildirim, kaynak error state'e geçer | Unit |
| Bir kaynak fail, diğerleri başarılı | Başarılı kaynaklar normal devam eder, fail eden kaynağın hatası izole | Unit |

### 9.4 Digest Üretim

| Senaryo | Beklenen Sonuç | Tip |
|---------|----------------|-----|
| Yeterli makale + aktif LLM key | Digest `ready` statüsünde, section'lar yazılır, bildirim gönderilir | Integration |
| Tüm LLM key'ler başarısız | Digest `failed`, admin'e hata bildirimi, `AllProvidersFailedError` | Unit |
| LLM çıktısı parse edilemez | Digest `failed`, hata loglanır | Unit |
| Aynı dönem için tekrar tetikleme | Mevcut digest güncellenir (idempotent), duplicate oluşmaz | Integration |

### 9.5 RAG Chatbot

| Senaryo | Beklenen Sonuç | Tip |
|---------|----------------|-----|
| Geçerli soru, yeterli context | Yanıt + kaynak referansları döner, chat_history'ye yazılır | Integration |
| Soru soruldu ama threshold üstü chunk yok | "Bu konuda elimde yeterli veri yok" yanıtı | Unit |
| Boş soru gönderildi | 422, VALIDATION_ERROR | Integration |
| Chatbot rate limit aşımı (21. istek/dk) | 429, RATE_LIMIT_EXCEEDED | Integration |

### 9.6 Audit Log

| Senaryo | Beklenen Sonuç | Tip |
|---------|----------------|-----|
| User login → audit log yazılır | `user.login` event, actor_user_id doğru | Integration |
| Source silme → audit log yazılır | `source.deleted` event, payload source detayını içerir | Integration |
| Failed login → IP loglanır | `user.login_failed` event, payload'da IP adresi | Integration |
| Audit log ve ana operasyon aynı transaction | Ana operasyon fail → audit log da rollback | Integration |

---

## 10. Test Çalıştırma Komutları

| Komut | Açıklama |
|-------|----------|
| `pytest tests/unit -v` | Tüm unit testleri çalıştır |
| `pytest tests/integration -v` | Tüm integration testleri çalıştır |
| `pytest tests/ -v --cov=apps --cov=services --cov=packages` | Tüm testler + coverage raporu |
| `pytest tests/ -k "test_auth"` | Yalnızca auth testlerini çalıştır |
| `pytest tests/ -x` | İlk fail'de dur |
| `pytest tests/ --cov-report=html` | HTML coverage raporu üret (`htmlcov/`) |

Dev ortamında testler `DATABASE_URL` olarak local PostgreSQL'e bağlanır. CI ortamında testcontainers veya GitHub Actions service container kullanılır.

---

*Bu doküman YıldızHolding Global Intelligence Platform mimari kararlarından türetilmiştir. Kararlar değiştiğinde doküman yeniden üretilir.*

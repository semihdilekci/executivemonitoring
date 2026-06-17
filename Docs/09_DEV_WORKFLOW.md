# 09 — Geliştirme İş Akışı

> **Platform:** YıldızHolding Global Intelligence Platform (YGIP)
> **Kapsam:** Local ortam kurulumu, branch stratejisi, commit convention, PR süreci, CI/CD pipeline, Cursor agent kuralları, environment yönetimi, migration iş akışı, code review kontrol listesi

---

## 1. Local Geliştirme Ortamı

### 1.1 Ön Gereksinimler

| Araç | Versiyon | Amaç |
|------|----------|------|
| Python | 3.12+ | Backend, collector'lar, processor, AI engine |
| Node.js | 20 LTS+ | Next.js web frontend |
| PostgreSQL | 16+ (pgvector dahil) | Birincil veritabanı |
| Redis | 7+ veya Upstash CLI | Cache, dedup, rate limit |
| Docker | 24+ | PostgreSQL + Redis local container |
| Git | 2.40+ | Versiyon kontrol |
| AWS CLI | 2.x | AWS servis erişimi (dev ortamı) |

### 1.2 İlk Kurulum

```bash
# 1. Repository klonla
git clone git@github.com:yildizholding/ygip.git
cd ygip

# 2. Python ortamı
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Node ortamı (web frontend)
cd apps/web
npm install
cd ../..

# 4. Environment değişkenleri
cp .env.example .env
# .env dosyasını düzenle: DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, vb.

# 5. Docker ile PostgreSQL + Redis
docker compose up -d

# 6. DB migration
alembic upgrade head

# 7. Seed data
python scripts/seed.py

# 8. Backend başlat
uvicorn apps.api.main:app --reload --port 8000

# 9. Frontend başlat (ayrı terminal)
cd apps/web && npm run dev
```

### 1.3 Docker Compose

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ygip_dev
      POSTGRES_USER: ygip
      POSTGRES_PASSWORD: ygip_dev_pass
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

### 1.4 .env.example

```bash
# Database
DATABASE_URL=postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=                    # openssl rand -base64 32

# CORS
CORS_ORIGINS=http://localhost:3000

# AWS (dev)
AWS_REGION=eu-west-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# LLM API key encryption (dev — local symmetric key)
ENCRYPTION_KEY=                    # openssl rand -base64 32

# Mail (dev — SES sandbox)
SES_SENDER_EMAIL=
SES_REGION=eu-west-1

# FCM
FCM_SERVICE_ACCOUNT_PATH=

# Environment
ENVIRONMENT=development
```

Yeni environment variable eklendiğinde `.env.example` aynı commit'te güncellenir. Değer yazılmaz, yalnızca key ismi eklenir.

---

## 2. Branch Stratejisi

### 2.1 Branch Yapısı

```
main                          → Production-ready kod, doğrudan push yasak
├── feature/mvp-0             → MVP-0 geliştirme branch'i
├── feature/mvp-1             → MVP-1 geliştirme branch'i (MVP-0 merge sonrası)
├── feature/mvp-2             → MVP-2 geliştirme branch'i
└── feature/mvp-3             → MVP-3 geliştirme branch'i
```

Her MVP fazı kendi feature branch'inde geliştirilir. `main` branch'e merge yalnızca faz tamamlandığında ve onay alındıktan sonra yapılır.

### 2.2 Kurallar

- `main` branch'e doğrudan push yapılamaz. Branch protection aktiftir.
- Her feature branch `main`'den oluşturulur.
- Feature branch içinde iterasyonlar sıralı commit'lerle ilerler — alt branch açılmaz.
- Merge yalnızca PR üzerinden yapılır: CI pass + en az 1 approval zorunludur.
- Merge stratejisi: squash merge (temiz commit geçmişi).
- Conflict durumunda feature branch `main`'den rebase alır.

### 2.3 Faz Tamamlama Akışı

```
1. feature/mvp-0 branch'inde tüm iterasyonlar tamamlanır
2. Smoke test geçer
3. PR açılır: feature/mvp-0 → main
4. Code review + approval
5. Squash merge → main
6. main'den production deploy
7. feature/mvp-1 branch'i main'den oluşturulur
```

---

## 3. Commit Convention

Conventional Commits standardı uygulanır. Her commit mesajı şu formatta olmalıdır:

```
<type>: <description>
```

### 3.1 Commit Tipleri

| Tip | Kullanım | Örnek |
|-----|----------|-------|
| `feat` | Yeni özellik | `feat: add login endpoint with JWT` |
| `fix` | Hata düzeltme | `fix: handle expired refresh token in auth service` |
| `refactor` | Kod iyileştirme (davranış değişmez) | `refactor: extract password validation to utility` |
| `test` | Test ekleme/düzeltme | `test: add integration tests for user CRUD` |
| `chore` | Araç, config, bağımlılık güncellemesi | `chore: add pytest-asyncio to dev dependencies` |
| `docs` | Dokümantasyon | `docs: update .env.example with SES variables` |

### 3.2 Kurallar

- Açıklama İngilizce yazılır.
- İlk harf küçük, nokta konmaz.
- Maksimum 72 karakter.
- Body opsiyoneldir; gerekiyorsa boş satır bırakılarak eklenir.
- Breaking change varsa: `feat!: description` veya body'de `BREAKING CHANGE:` notu.

### 3.3 İterasyon Bazlı Commit Önerisi

Her Cursor Composer iterasyonu 1-3 commit üretir:

```
feat: add FastAPI boilerplate with health endpoint        ← ana iş
test: add integration test for health endpoint            ← test
chore: configure CORS middleware and rate limiter          ← config/yardımcı
```

İterasyon büyükse (3+ commit) her commit kendi başına çalışır durumda olmalıdır — yarım bırakılmış commit yasaktır.

---

## 4. PR Süreci

### 4.1 PR Açma

PR başlığı iterasyon tanımını yansıtır:

```
feat: [MVP-0 / Faz 1 / 1.3] Auth login/refresh/logout endpoints
```

PR açıklaması şu bilgileri içerir:
- Hangi iterasyon (faz + numara)
- Ne yapıldı (bullet list)
- Test durumu (hangi testler eklendi/güncellendi)
- Migration var mı (evet/hayır)
- Yeni env var var mı (evet/hayır, varsa `.env.example` güncellendi mi)

### 4.2 PR Kontrol Listesi

PR açmadan önce doğrulanması gerekenler:

- [ ] Tüm testler local'de geçiyor (`pytest tests/ -v`)
- [ ] Lint hatası yok (`ruff check .`)
- [ ] Type check hatası yok (`mypy apps/ services/ packages/`)
- [ ] Yeni env var varsa `.env.example` güncellendi
- [ ] Yeni DB tablosu varsa migration dosyası oluşturuldu
- [ ] Yeni API endpoint varsa OpenAPI şeması doğru üretiliyor
- [ ] Yeni collector varsa `BaseCollector` implement edildi

### 4.3 CI Gate

PR açıldığında GitHub Actions otomatik çalışır:

```
Lint (ruff)          → ~10 sn
Type check (mypy)    → ~30 sn
Unit test (pytest)   → ~1-2 dk
Integration test     → ~2-3 dk
Coverage report      → fail-under=70
```

Tüm aşamalar geçmeden PR merge edilemez.

### 4.4 Review ve Merge

- En az 1 reviewer approval zorunludur.
- Reviewer ilgili dosyaları inceler, güvenlik açığı, performans sorunu ve test eksikliği kontrolü yapar.
- Approval sonrası squash merge yapılır.
- Merge sonrası feature branch silinmez (faz devam ediyorsa).

---

## 5. CI/CD Pipeline

### 5.1 Test Pipeline (Her PR)

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
      - name: Coverage check
        run: coverage report --fail-under=70
```

### 5.2 Deploy Pipeline (Main Merge Sonrası)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: eu-west-1
      - name: Deploy API (Lambda/ECS)
        run: ./scripts/deploy-api.sh
      - name: Deploy collectors (Lambda)
        run: ./scripts/deploy-collectors.sh
      - name: Deploy web (S3 + CloudFront)
        run: ./scripts/deploy-web.sh
      - name: Run migrations
        run: ./scripts/run-migration.sh
```

Deploy script'leri Faz 8'de (production deploy) oluşturulur. Dev ortamında deploy manual veya ayrı workflow ile yapılır.

---

## 6. Cursor / Claude Code Agent Kuralları

### 6.1 Yasak Aksiyonlar

Aşağıdaki aksiyonlar kullanıcı (Semih) onayı olmadan yapılamaz:

| # | Yasak Aksiyon | Gerekçe |
|---|--------------|---------|
| 1 | `main` branch'e doğrudan push veya merge | Production koruması |
| 2 | `.env` veya secrets dosyasına API key yazma | Secret sızıntı riski |
| 3 | DB migration'ı production ortamında onaysız çalıştırma | Veri kaybı riski |
| 4 | `sources` tablosuna onaysız kayıt ekleme/silme | Veri toplama bütünlüğü |
| 5 | LLM prompt şablonunu onaysız production'a alma | AI çıktı kalitesi |
| 6 | Herhangi bir AWS kaynak silme komutu çalıştırma | Altyapı koruması |

Agent PR açar, açıklama yazar, review için bekler. Merge yetkisi yalnızca Semih'tedir.

### 6.2 İterasyon Başlatma Protokolü

Her Cursor Composer oturumu şu adımlarla başlar:

1. **Context yükleme:** İterasyon tanımındaki "Cursor context" dosyaları Composer'a eklenir.
2. **Instruction:** İterasyon açıklaması Composer'a verilir. Örnek: "Faz 1, iterasyon 1.3: Auth login/refresh/logout endpoint'lerini oluştur. 10_IMPLEMENTATION_ROADMAP.md'deki 1.3 tanımına uy."
3. **Çıktı doğrulama:** Üretilen kodun testlerle birlikte çalıştığı doğrulanır.
4. **Commit:** Conventional commit formatında commit yapılır.

### 6.3 Agent İş Akışı

```
Semih: iterasyon instruction verir
  ↓
Agent: kodu üretir + testleri yazar
  ↓
Semih: local'de çalıştırır, doğrular
  ↓
Semih: commit yapar (veya agent'a onay verir)
  ↓
Sonraki iterasyona geç
```

Agent bir iterasyonu tamamladığında sonraki iterasyona otomatik geçmez — Semih'in onayını bekler.

### 6.4 Context Yönetimi İlkeleri

- Her iterasyonda yalnızca ilgili dosyalar context'e eklenir. Tüm repository context'e yüklenmez.
- Önceki iterasyonun çıktı dosyaları sonraki iterasyonun context'ine dahil edilir.
- Model dosyaları (`packages/shared/models/`) çoğu iterasyonda context'te olmalıdır.
- Mimari kararlar dokümanı (`mimari-kararlar.md`) Faz 0 ve büyük tasarım kararları gerektiren iterasyonlarda context'e eklenir; her iterasyonda gerekmez.
- Bu doküman (`09_DEV_WORKFLOW.md`) ve roadmap (`10_IMPLEMENTATION_ROADMAP.md`) iterasyon başında referans alınır, Composer context'ine eklenmez (instruction olarak verilir).

---

## 7. Environment Yönetimi

### 7.1 Ortam Tanımları

| Ortam | Amaç | AWS Kaynak Prefix | DB | Erişim |
|-------|------|-------------------|----|----|
| `development` | Local geliştirme | — (Docker local) | ygip_dev (local) | Geliştirici |
| `dev` | AWS dev ortamı | `ygip-dev-` | ygip-dev-db (RDS t3.micro) | Geliştirici |
| `production` | Canlı sistem | `ygip-prod-` | ygip-prod-db (RDS t3.micro→t3.small) | Tüm kullanıcılar |

Staging ortamı MVP-0'da yoktur. Test, local development ve AWS dev ortamında yapılır.

### 7.2 Environment Variable Çözümleme

```python
# apps/api/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET_KEY: str
    CORS_ORIGINS: str = "http://localhost:3000"
    AWS_REGION: str = "eu-west-1"
    ENCRYPTION_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

Production ortamında `.env` dosyası kullanılmaz. Tüm değerler AWS Secrets Manager'dan veya Lambda/ECS environment variable olarak inject edilir.

### 7.3 Ortam İzolasyonu Kontrol Listesi

- [ ] Dev Lambda fonksiyonları yalnızca `ygip-dev-*` kaynaklarına erişebilir (IAM ARN scope)
- [ ] Prod Lambda fonksiyonları yalnızca `ygip-prod-*` kaynaklarına erişebilir
- [ ] Dev ortamından prod RDS'e bağlantı IAM ile engellenmiş
- [ ] Secret'lar ortam bazlı ayrı Secrets Manager entry'lerinde (`ygip/dev/*`, `ygip/prod/*`)
- [ ] Production verisi dev ortamına kopyalanamaz

---

## 8. Database Migration İş Akışı

### 8.1 Migration Oluşturma

```bash
# Yeni migration oluştur (model değişikliğinden sonra)
alembic revision --autogenerate -m "add_notification_logs_table"

# Migration dosyasını incele ve düzenle
# alembic/versions/004_add_notification_logs_table.py

# Migration uygula (local)
alembic upgrade head

# Geri al (gerekirse)
alembic downgrade -1
```

### 8.2 Migration Kuralları

- Her yeni tablo veya şema değişikliği migration dosyası gerektirir.
- Migration dosyası `upgrade()` ve `downgrade()` fonksiyonlarını içerir. Downgrade her zaman yazılır.
- Autogenerate çıktısı manuel incelenir — özellikle `JSONB`, `ARRAY`, `vector` gibi özel tipler doğrulanır.
- Veri kaybına yol açabilecek migration'lar (kolon silme, tip değişikliği) ayrı PR'da, açık uyarıyla gönderilir.
- Production migration onaysız çalıştırılamaz (agent yasak listesi #3).

### 8.3 Migration Adlandırma

```
alembic/versions/
  001_core_tables.py           → users, system_settings, password_reset_tokens, audit_logs
  002_data_tables.py           → sources, raw_items, processed_items, embeddings, api_keys, api_usage_logs
  003_content_tables.py        → prompt_templates, digests, digest_sections, chat_history, notification_logs
  004_add_{table_name}.py      → Sonraki migration'lar açıklayıcı isimle
```

### 8.4 Seed Data Yönetimi

```bash
# Dev ortamına seed data yükle
python scripts/seed.py

# Seed idempotent'tir — tekrar çalıştırılabilir
# Var olan kayıtları atlar, eksikleri ekler
```

Seed script `fixtures/` klasöründeki JSON dosyalarını okur. Production seed ayrı script ile yapılır (`scripts/seed_prod.py`) ve yalnızca admin kullanıcısı + system_settings + source tanımlarını içerir. Test verileri (fixture articles, sample digests) production'a yüklenmez.

---

## 9. Code Review Kontrol Listesi

Reviewer her PR'da aşağıdaki maddeleri kontrol eder:

### 9.1 Güvenlik

- [ ] Yeni endpoint'e uygun guard eklenmiş mi? (`require_admin` veya `require_authenticated`)
- [ ] Kullanıcı girdisi Pydantic ile validate ediliyor mu?
- [ ] Raw SQL kullanılmamış, ORM parametrik sorgu kullanılmış mı?
- [ ] API yanıtında `password_hash`, `encrypted_key` gibi hassas alan dönmüyor mu?
- [ ] Yeni env var `.env.example`'a eklenmiş mi?
- [ ] Secret veya API key koda hardcode edilmemiş mi?
- [ ] Hata mesajında iç detay sızmıyor mu? (stack trace, DB bilgisi)

### 9.2 Kalite

- [ ] Unit/integration test yazılmış mı?
- [ ] Test edge case'leri kapsıyor mu? (boş girdi, geçersiz ID, yetki kontrolü)
- [ ] Naming convention'a uyulmuş mu? (snake_case Python, camelCase TS, PascalCase class)
- [ ] Gereksiz yorum veya dead code yok mu?
- [ ] Hata yönetimi doğru mu? (uygun exception tipi, anlamlı mesaj)

### 9.3 Mimari

- [ ] Yeni collector `BaseCollector` implement ediyor mu?
- [ ] Katman sınırları korunmuş mu? (router → service → repository, kısa devre yok)
- [ ] Yeni tablo varsa migration dosyası var mı?
- [ ] Audit log gerekiyorsa (`audit_service.log_event`) çağrılmış mı?
- [ ] Yeni endpoint endpoint yetki matrisine eklenmiş mi?

---

## 10. Naming Convention Referansı

| Hedef | Convention | Örnek |
|-------|-----------|-------|
| Klasör / dosya | kebab-case | `ai-engine/`, `llm_client.py` (Python dosyaları snake_case) |
| Python class | PascalCase | `RSSCollector`, `DigestGenerator` |
| Python fonksiyon / değişken | snake_case | `create_access_token()`, `user_service` |
| TypeScript fonksiyon / değişken | camelCase | `useDigests()`, `apiClient` |
| React component dosyası | PascalCase.tsx | `DigestCard.tsx`, `ChatMessage.tsx` |
| DB tablo | snake_case, çoğul | `users`, `digest_sections`, `audit_logs` |
| DB kolon | snake_case | `created_at`, `source_id`, `content_hash` |
| Environment variable | UPPER_SNAKE_CASE | `DATABASE_URL`, `JWT_SECRET_KEY` |
| Commit mesajı | Conventional Commits | `feat: add login endpoint` |
| Branch | kebab-case | `feature/mvp-0` |
| API endpoint | kebab-case, çoğul | `/api/v1/audit-logs`, `/api/v1/api-keys` |

---

## 11. Yardımcı Komutlar

| Komut | Açıklama |
|-------|----------|
| `uvicorn apps.api.main:app --reload` | Backend dev server (hot reload) |
| `cd apps/web && npm run dev` | Frontend dev server |
| `pytest tests/ -v` | Tüm testler |
| `pytest tests/unit -v` | Yalnızca unit testler |
| `pytest tests/integration -v` | Yalnızca integration testler |
| `pytest tests/ -k "test_auth"` | Belirli testler |
| `pytest tests/ --cov=apps --cov-report=html` | Coverage raporu (htmlcov/) |
| `ruff check .` | Lint kontrolü |
| `ruff format .` | Otomatik format |
| `mypy apps/ services/ packages/` | Type check |
| `alembic upgrade head` | Migration uygula |
| `alembic downgrade -1` | Son migration'ı geri al |
| `alembic revision --autogenerate -m "desc"` | Yeni migration oluştur |
| `python scripts/seed.py` | Dev seed data yükle |
| `docker compose up -d` | PostgreSQL + Redis başlat |
| `docker compose down` | Container'ları durdur |

---

*Bu doküman YıldızHolding Global Intelligence Platform mimari kararlarından türetilmiştir. Kararlar değiştiğinde doküman yeniden üretilir.*

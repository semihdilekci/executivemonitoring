# YıldızHolding Global Intelligence Platform (YGIP)

Tek kiracılı dahili kurumsal izleme platformu: dış kaynaklardan veri toplama, işleme pipeline'ı, AI digest üretimi ve RAG chatbot.

Detaylı proje tanımı: [Docs/00_PROJECT_OVERVIEW.md](Docs/00_PROJECT_OVERVIEW.md)

## Monorepo Yapısı

| Dizin | Amaç |
|-------|------|
| `apps/api/` | FastAPI HTTP sunucusu |
| `apps/web/` | Next.js web dashboard |
| `apps/mobile/` | React Native mobil uygulama |
| `services/collectors/` | Veri toplama worker'ları |
| `services/processor/` | Veri işleme pipeline |
| `services/ai-engine/` | Digest, RAG, chatbot |
| `packages/shared/` | Ortak SQLAlchemy modelleri ve enum'lar |
| `infra/` | AWS IaC (CDK/Terraform) |
| `fixtures/` | Geliştirme test verisi (sentetik) |
| `tests/` | pytest unit + integration testleri |

## Ön Gereksinimler

| Araç | Versiyon |
|------|----------|
| Python | 3.12+ |
| Node.js | 20 LTS+ |
| PostgreSQL | 16+ (pgvector) |
| Redis | 7+ |
| Docker | 24+ |
| Git | 2.40+ |

## Kurulum

```bash
# Python ortamı
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Node ortamı (web + mobil scaffold)
npm install

# Environment
cp .env.example .env
# .env dosyasını düzenleyin (değer yazmayın — local secret'lar commit edilmez)

# Altyapı servisleri (PostgreSQL + Redis)
docker compose up -d
```

### Veritabanı migration

```bash
# docker compose sonrası
alembic upgrade head

# Geri alma doğrulaması (opsiyonel)
alembic downgrade -1
alembic upgrade head
```

Local DB: `.env` içindeki `DATABASE_URL` (şablon: `.env.example`) — test, migration ve seed bu değeri kullanır.  
CI test DB: `postgresql+asyncpg://test:test@localhost:5432/ygip_test` (GitHub Actions ortam değişkeni)

### Dev seed data

```bash
python scripts/seed.py
```

Script idempotent'tir — tekrar çalıştırıldığında mevcut kayıtları atlar.

**Dev kullanıcıları** (`fixtures/users.json` — yalnızca local/test):

| E-posta | Rol | Şifre (dev only) |
|---------|-----|------------------|
| `admin@ygip.test` | admin | `DevPass1` |
| `viewer1@ygip.test` | viewer | `DevPass1` |
| `viewer2@ygip.test` | viewer | `DevPass1` |

Production verisi `fixtures/` dizinine taşınmaz.

## Geliştirme

- Tüm MVP-0 geliştirmesi `feature/mvp-0` branch'inde yapılır.
- `main` branch'e doğrudan push yasaktır — PR + CI + onay zorunludur.

### Kalite Kontrolleri

```bash
ruff check .
ruff format --check .
mypy apps/ services/ packages/
pytest tests/unit -v
pytest tests/integration -v  # `.env` DATABASE_URL gerekir; bağlantı yoksa anlamlı skip mesajı
```

CI pipeline (her PR): `.github/workflows/test.yml` — lint → mypy → unit → integration → coverage (%70).

## Dokümantasyon

| Dosya | İçerik |
|-------|--------|
| [Docs/00_PROJECT_OVERVIEW.md](Docs/00_PROJECT_OVERVIEW.md) | Proje kimliği ve MVP fazları |
| [Docs/09_DEV_WORKFLOW.md](Docs/09_DEV_WORKFLOW.md) | Branch, commit, CI/CD |
| [Docs/10_IMPLEMENTATION_ROADMAP.md](Docs/10_IMPLEMENTATION_ROADMAP.md) | Faz iterasyon planı |

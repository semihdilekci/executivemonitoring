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
```

> **Not:** DB migration, seed ve uygulama başlatma adımları Faz 1+ iterasyonlarında eklenecektir.

## Geliştirme

- Tüm MVP-0 geliştirmesi `feature/mvp-0` branch'inde yapılır.
- `main` branch'e doğrudan push yasaktır — PR + CI + onay zorunludur.

### Kalite Kontrolleri

```bash
ruff check .
ruff format --check .
mypy apps/ services/ packages/
pytest tests/unit -v
```

## Dokümantasyon

| Dosya | İçerik |
|-------|--------|
| [Docs/00_PROJECT_OVERVIEW.md](Docs/00_PROJECT_OVERVIEW.md) | Proje kimliği ve MVP fazları |
| [Docs/09_DEV_WORKFLOW.md](Docs/09_DEV_WORKFLOW.md) | Branch, commit, CI/CD |
| [Docs/10_IMPLEMENTATION_ROADMAP.md](Docs/10_IMPLEMENTATION_ROADMAP.md) | Faz iterasyon planı |

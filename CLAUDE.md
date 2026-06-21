# CLAUDE.md — YıldızHolding Global Intelligence Platform (YGIP)

> Bu proje **`.cursor/rules/*.mdc`** altında tanımlı kural seti ile yönetilir.
> Bu dosya always-apply + glob + göreve-bağlı kuralların **yönlendiricisidir**.
> **Spec tek doğruluk kaynağı:** `Docs/`. `.mdc` ile Docs çelişirse **Docs kazanır**.

---

## Çalışma Protokolü — Her Görevde

1. **Her zaman geçerli (00–04)** — özet aşağıda; tereddütte tam `.mdc` oku.
2. **Dosyaya dokunmadan önce** glob tablosundan ilgili kuralı oku.
3. **Görev prosedürüyse** (endpoint, ekran, migration…) how-to tablosundan ilgili `4x` kuralı oku.
4. **Faz çalışmasıysa** (`Faz N — İterasyon M`) ilgili `@50-phase-XX-slug` oku.
5. Spec detayı için `Docs/` path'ine git — rule'da kopyalanmış tablo arama.

> **Verimlilik:** Tüm `.mdc` dosyalarını okuma. Yalnızca dokunduğun dosya + görev tipine uygun kurallar.

---

## Her Zaman Geçerli (00–04 özet)

Tam metin: `.cursor/rules/0*.mdc`, `04-quality-gates.mdc`.

- **[00] Kimlik** — YGIP: veri toplama → pipeline → AI digest + RAG chatbot. Stack: FastAPI, SQLAlchemy, Next.js, React Native, AWS Lambda/SQS.
- **[01] Felsefe** — MVP-0 scope, iterasyon disiplini, test gömülü, agent `main`'e merge edemez.
- **[02] Naming** — TR UI / EN code; Conventional Commits (`Docs/09` §3); `feature/mvp-N` branch (`Docs/09` §2).
- **[03] Güvenlik** — JWT, RBAC, audit transaction, raw SQL yasak, secret commit yasak.
- **[04] Kalite** — pytest coverage eşikleri, ruff+mypy CI (`Docs/09` §5), auth/RBAC ≥%90.

---

## Glob Yönlendirme

| Dosya deseni | Oku |
| --- | --- |
| `apps/api/**/*.py`, `services/**/*.py` | `10-backend-architecture` |
| `apps/api/**/routers/auth.py`, `**/services/auth*` | `11-auth-jwt` |
| `apps/api/**/core/deps.py`, `**/guards/**` | `12-rbac-guards` |
| `services/collectors/**` | `13-collectors` |
| `apps/api/**/routers/*.py` | `14-fastapi-routers` |
| `packages/shared/models/**`, `alembic/**` | `15-database-alembic` |
| `apps/api/**/audit*` | `16-audit` |
| `services/processor/**` | `17-processor-pipeline` |
| `services/ai-engine/**` | `18-ai-engine` |
| `apps/web/**` | `20-frontend-next` |
| `apps/web/src/app/**` | `21-next-routes` |
| `apps/web/**/*Form*`, `**/new/**`, `**/edit/**` | `22-forms` |
| `apps/web/**/hooks/**`, `**/*Query*` | `23-react-query` |
| `apps/web/src/components/**` | `24-components` |
| `apps/web/**/*.tsx` | `25-a11y` |
| `apps/mobile/**` | `27-mobile-react-native` |
| `infra/**` | `30-infra-aws` |
| `tests/**`, `**/test_*.py` | `35-testing-pytest` |

Birden fazla desen eşleşebilir — hepsini uygula.

---

## How-To Yönlendirme

| Görev türü | Oku |
| --- | --- |
| Yeni REST endpoint | `40-add-new-endpoint` |
| Yeni ekran (`S-*`) | `41-add-new-screen` |
| Alembic migration | `42-add-alembic-migration` |
| RBAC / admin guard | `43-add-rbac-guard` |
| Legacy → pattern | `44-refactor-to-pattern` |
| Mimari karar kaydı | `45-write-adr` |
| CI / test kırığı | `46-fix-failing-test` |
| Yeni collector | `47-add-collector` |
| Faz branch + iterasyon | `48-git-phase-branch` |

---

## Faz Yönlendirme (MVP-0)

Mesajda **「Faz N — İterasyon M」** belirt. Kod öncesi `48-git-phase-branch` (`feature/mvp-0` branch).

| Faz | Kapsam | Kural |
| --- | --- | --- |
| 0 | Altyapı ve iskelet | `@50-phase-00-infra-scaffold` |
| 1 | Backend core | `@51-phase-01-backend-core` |
| 2 | Collector'lar | `@52-phase-02-collectors` |
| 3 | Processor pipeline | `@53-phase-03-processor` |
| 4 | AI engine | `@54-phase-04-ai-engine` |
| 5 | Bildirim backend | `@55-phase-05-notifications` |
| 6 | Web frontend | `@56-phase-06-web-frontend` |
| 6.1 | Pipeline monitoring kokpiti | `@59-phase-061-pipeline-monitoring` |
| 6.2 | İçerik Arşivi (admin) | `@60-phase-062-content-archive` |
| 7 | Mobil | `@57-phase-07-mobile` |
| 8 | Pipeline runtime (Lambda deploy) | `@58-phase-08-pipeline-runtime` |

---

## Docs/ — Nihai Kaynak

| Dosya | İçerik |
| --- | --- |
| `Docs/00_PROJECT_OVERVIEW.md` | Kimlik, MVP fazları, stack |
| `Docs/01_DOMAIN_MODEL.md` | Entity, pipeline |
| `Docs/02_DATABASE_SCHEMA.md` | Tablo, migration |
| `Docs/03_API_CONTRACTS.md` | REST sözleşmeleri |
| `Docs/04_BACKEND_SPEC.md` | FastAPI, collector, AI |
| `Docs/05_FRONTEND_SPEC.md` | Next.js, RN |
| `Docs/06_SCREEN_CATALOG.md` | `S-*` ekranlar |
| `Docs/07_SECURITY_IMPLEMENTATION.md` | JWT, RBAC, audit |
| `Docs/08_TESTING_STRATEGY.md` | pytest, CI |
| `Docs/09_DEV_WORKFLOW.md` | Local setup, branch, commit, PR, CI/CD, agent kuralları |
| `Docs/10_IMPLEMENTATION_ROADMAP.md` | Faz 0–8 iterasyonları |
| `Docs/mimari-kararlar.md` | Mimari kararlar özeti (ADR kaynağı) |

---

## Skills

| Skill | Ne zaman |
| --- | --- |
| `phase-creator` | Faz `.mdc` + blueprint iterasyonlar (50–58); `Docs/` önce, plan-modu kalitesi |
| `phase-controller` | Implementasyon sonrası gap audit |
| `rules-architect` | Rules mimarisi güncelleme |

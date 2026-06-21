# Branch Protection Kurulumu

Bu dosya GitHub repo yöneticisi için manuel kurulum notlarıdır. CI workflow (`.github/workflows/test.yml`) merge öncesi otomatik çalışır; aşağıdaki ayarlar `main` branch'i korur.

## `main` branch kuralları

GitHub → **Settings** → **Branches** → **Add branch protection rule**

| Ayar | Değer |
|------|-------|
| Branch name pattern | `main` |
| Require a pull request before merging | ✓ |
| Required approvals | 1 |
| Dismiss stale pull request approvals when new commits are pushed | ✓ (önerilir) |
| Require status checks to pass before merging | ✓ |
| Required status checks | `test` (workflow job adı) |
| Require branches to be up to date before merging | ✓ |
| Do not allow bypassing the above settings | ✓ |
| Restrict who can push to matching branches | ✓ (yalnızca admin/deploy bot) |
| Allow force pushes | ✗ |
| Allow deletions | ✗ |

## `feature/mvp-0` branch

- MVP-0 geliştirmesi bu branch üzerinde yapılır (`Docs/09_DEV_WORKFLOW.md` §2).
- Doğrudan `main`'e push yasaktır; faz sonunda `feature/mvp-0` → `main` PR açılır.
- Faz devam ederken feature branch silinmez.

## CI gate sırası

```
Lint (ruff) → Type check (mypy) → Unit test → Integration test → Coverage (fail-under=70)
```

Detay: `Docs/09_DEV_WORKFLOW.md` §4.3 ve §5.1.

## Deploy workflow

`deploy-dev.yml` (Faz 8.5) dev stack'i (`YgipDevStack`) **manuel** (`workflow_dispatch`) deploy eder — maliyet kontrolü için otomatik push tetikleme yoktur. Gerekli secret'lar `dev` GitHub environment'ında tutulur: `AWS_DEV_DEPLOY_ROLE_ARN` (OIDC), `DEV_DATABASE_URL`, `DEV_REDIS_URL`. Detay: `infra/README.md`, `Docs/09` §5.3.

Production deploy workflow'u (`prod-ygip-*`) MVP-1 Production Launch sprint'inde eklenir.

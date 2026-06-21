# Katman Taksonomisi — .mdc Mimarisi

Lean Management `.cursor/rules/` paketinden türetilmiş **4 katmanlı** model. Yeni projelerde aynı mantık; numara aralıkları ve dosya adları projeye göre uyarlanır.

## Neden katman?

| Problem | Çözüm |
| ------- | ----- |
| 47 kural × ~250 satır = context patlaması | Tetiklemeye göre yükleme |
| Spec rule'da eskir | `docs/` tek doğruluk kaynağı; rule referans |
| Agent hangi kuralı okuyacağını bilmez | `CLAUDE.md` router + description trigger |
| Her görevde aynı 6 güvenlik maddesi unutulur | `alwaysApply` çekirdek (00–04) |

---

## Katman 0 — Çekirdek (00–04)

| Özellik | Değer |
| ------- | ----- |
| Frontmatter | `alwaysApply: true` |
| Ne zaman yüklenir | **Her oturum** |
| Satır hedefi | 100–170 / dosya; **toplam ≤800** |
| İçerik tipi | Prensip, checklist, pin'li stack, MVP sınırları |

### Standart dosyalar

| NN | Slug | İçerik |
| -- | ---- | ------ |
| 00 | `project-identity` | Proje kimliği, stack, monorepo, domain sözlüğü, non-goals |
| 01 | `coding-philosophy` | MVP scope, test-first, self-review, vibe coding disiplini |
| 02 | `language-naming` | TR UI / EN code, commit, error code pattern |
| 03 | `security-baseline` | Her değişiklikte 6 zorunlu kontrol (executable checklist) |
| 04 | `quality-gates` | Coverage, lint, bundle, CI, a11y eşikleri |

**Ne koyma:** Modül pattern'leri, endpoint prosedürü, ekran şablonu → alt katmanlara.

---

## Katman 1 — Domain glob (10–39)

| Özellik | Değer |
| ------- | ----- |
| Frontmatter | `description` + `globs: [...]` |
| Ne zaman yüklenir | Eşleşen dosya düzenlenirken |
| Satır hedefi | 250–400 / dosya |

### Numara blokları (Lean Management referans)

| Aralık | Alan | Örnek glob |
| ------ | ---- | ---------- |
| 10–19 | Backend genel + modül | `apps/api/**/*.ts` |
| 11 | Auth | `apps/api/src/auth/**` |
| 12 | Permissions | `apps/api/src/roles/**`, `shared-types/permissions.ts` |
| 13 | Processes/tasks | `apps/api/src/processes/**`, `tasks/**` |
| 14 | Controllers | `apps/api/**/*.controller.ts` |
| 15 | Database/Prisma | `apps/api/prisma/**`, `**/*.service.ts` |
| 16 | Audit | `apps/api/src/audit/**` |
| 20–29 | Frontend | `apps/web/src/**` |
| 21 | Routes | `apps/web/src/app/**` |
| 22 | Forms | `*Form*.tsx`, `**/new/**`, `**/edit/**` |
| 23 | Queries | `**/queries/**`, `use*Query.ts` |
| 24 | Components | `apps/web/src/components/**` |
| 25 | a11y | `apps/web/**/*.tsx` |
| 26 | Design system | `apps/web/**/*.{tsx,css}`, `docs/design-system/**` |
| 30–39 | Infra, test | `infrastructure/**`, `**/*.{test,spec}.{ts,tsx}` |

**Glob tasarımı:**

- Genel kural (10, 20) **geniş** glob; spesifik (14, 22) **dar** glob.
- Aynı dosya birden fazla kural tetikleyebilir — bilinçli (controller = 10 + 14).
- Glob'u gereksiz genişletme: `**/*.ts` tüm repo = context waste.

---

## Katman 2 — How-to / prosedür (40–49)

| Özellik | Değer |
| ------- | ----- |
| Frontmatter | `description` only (trigger: WHAT + WHEN, İngilizce) |
| Ne zaman yüklenir | Agent görev tipine göre **requestable** |
| Satır hedefi | 200–350 / dosya |

### Tipik prosedürler

| NN | Slug | Tetikleyici görev |
| -- | ---- | ----------------- |
| 40 | `add-new-endpoint` | Yeni/değişen REST endpoint |
| 41 | `add-new-screen` | Yeni route/ekran |
| 42 | `add-prisma-migration` | Schema migration |
| 43 | `add-new-permission` | RBAC/ABAC permission |
| 44 | `refactor-to-pattern` | Legacy → pattern hizalama |
| 45 | `write-adr` | Mimari karar kaydı |
| 46 | `fix-failing-test` | CI/test kırığı |
| 47+ | domain-specific | Kritik ekran, UX fix, süreç tipi |
| 48 | `git-phase-branch` | Roadmap faz implementasyonu — zorunlu feature branch |

**Alt numara:** `47.1-screen-catalog-UX-fix` — aynı prosedür ailesinde varyant.

---

## Katman 3 — Faz (50–69)

| Özellik | Değer |
| ------- | ----- |
| Frontmatter | `description: '[Faz N] … — K iterasyon/chat (…). Mesajda "Faz N — İterasyon M" belirt.'` |
| Ne zaman yüklenir | Faz çalışması; `@NN-phase-XX-slug` invoke |
| Üretim | **`phase-creator` skill** — bu katman `rules-architect` Faz H'de devredilir |
| Satır hedefi | 200–500; iterasyon başına ~80–120 satır (blueprint) |

### Adlandırma

`NN-phase-XX-<kebab-slug>.mdc`

- `NN`: sıra (50, 51, 52, 52.1 …)
- `XX`: roadmap faz no
- Alt-faz: `52.1-phase-02-GoogleSSOAuth.mdc`

### İçerik (özet — tam iskelet `phase-creator/iteration-blueprint.md`)

- Goal (1–3 cümle)
- İterasyonlar: Hedef, Docs okuma sırası, Uygulama planı, Dosya kapsamı, Spec→kod, Kalite kapıları, Bu iterasyonda yok, Stop
- Required Context (`Docs/` path + §)
- Done Definition, Explicit Don'ts
- **Tekrarlanmaz:** API body, ekran alan tablosu, 50+ satır file tree

---

## Frontmatter karar ağacı

```
Her oturumda gerekli mi?
├─ Evet → alwaysApply: true (00–04 only)
└─ Hayır
    ├─ Belirli dosya yollarında mı?
    │   ├─ Evet → description + globs
    │   └─ Hayır (görev-tetikli prosedür/faz)
    │       └─ description only (agent-requestable)
```

### YAML örnekleri

**Çekirdek:**
```yaml
---
alwaysApply: true
---
```

**Glob:**
```yaml
---
description: Backend controllers — decorator stack, Zod pipe, permission, audit
globs:
  - "apps/api/**/*.controller.ts"
---
```

**How-to:**
```yaml
---
description: Step-by-step for adding a REST endpoint. Use when creating or modifying apps/api/**/controller.ts routes.
---
```

**Faz:**
```yaml
---
description: "[Faz 6] Task management — 2 iterasyon/chat (backend+SLA → FE+E2E). Mesajda \"Faz 6 — İterasyon N\" belirt."
---
```

---

## Context bütçesi (Lean Management ölçümü)

| Senaryo | Yaklaşık yük |
| ------- | ------------ |
| Oturum başı (alwaysApply) | ~732 satır (00–04) |
| + Backend controller edit | +~340 (10+14) |
| + Yeni endpoint görevi | +~330 (40 requestable) |
| Tüm 47 kural | ~11.600 satır — **asla hedefleme** |

**Kural:** Router'da "yalnızca dokunduğun dosyaya uygun kuralı oku" notu zorunlu.

---

## Yeni proje numaralandırma

1. 00–04 her projede aynı semantik (içerik projeye özel).
2. 10–39: stack'e göre blok ayır (Python backend → `10-django-*`; yoksa atla).
3. 40–49: en sık 5–8 prosedür yeter; geri kalanı ihtiyaç oldukça.
4. 50+: roadmap faz sayısı kadar; `phase-creator` ile üret.
5. Numara boşluğu bırak (13 atlandı, 47.1 eklendi) — refactoring kolaylığı.

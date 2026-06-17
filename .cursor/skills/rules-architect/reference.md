# Rules Architect — Referans

## docs/ → .mdc eşleme haritası

Spec **yalnızca** soldaki dosyada kalır. Sağdaki rule **distille pattern + referans** içerir.

| docs/ dosyası | Rule katmanı | Rule'da kalması gereken | Rule'da OLMAMASI gereken |
| ------------- | ------------ | ----------------------- | ------------------------ |
| `00_PROJECT_OVERVIEW` | 00 alwaysApply | MVP in/out, kullanıcı profili özeti | Tam KPI tablosu |
| `01_DOMAIN_MODEL` | 00 terimler; 10–13 glob | Entity adları, state machine **adı** | Geçiş tablosunun tamamı |
| `02_DATABASE_SCHEMA` | 15 glob | Prisma convention, migration disiplini | Kolon listesi |
| `03_API_CONTRACTS` | 14 glob; 40 how-to | Response envelope pattern | Request/response örnekleri |
| `04_BACKEND_SPEC` | 10 glob | Modül klasör yapısı, DI | Servis listesi |
| `05_FRONTEND_SPEC` | 20 glob | Route convention, state stratejisi | Tam route ağacı |
| `06_SCREEN_CATALOG` | 41, 47 how-to | Ekran ID formatı (`S-*`) | Alan listesi, UX state tablosu |
| `07_SECURITY_IMPLEMENTATION` | 03 alwaysApply; 11 glob | 6'lı checklist özeti | Threat model detayı |
| `08_TESTING_STRATEGY` | 04; 35 glob | Coverage eşikleri, piramit | Test dosya envanteri |
| `09_DEV_WORKFLOW` | 01, 02, 04 | Commit format, PR gate | CI yaml |
| `10_IMPLEMENTATION_ROADMAP` | 50+ phase (.mdc) | — (phase-creator üretir) | Faz kod detayı |
| `docs/adr/*` | 45 how-to; 00 pin kararlar | ADR numarası + 1 cümle karar | Tam MADR metni |

**Altın kural:** `.mdc` ile `docs/` çelişirse → **docs kazanır**; rule güncellenir.

---

## İçerik distilasyon kuralları

1. **Checklist > açıklama:** Güvenlik, Done Definition, Stop maddeleri checkbox.
2. **1 iyi / 1 kötü örnek:** Kod pattern'lerinde yeterli; 5 örnek yasak.
3. **Footer referans:** Her rule sonunda `Detay: docs/XX …` (1–3 path).
4. **Tablo sınırı:** Rule içi tablo ≤8 satır; daha uzun → docs.
5. **File tree sınırı:** ≤15 satır; daha uzun → "bkz. docs/04 Bölüm X".
6. **Tekrar yasağı:** Aynı 6 güvenlik maddesi yalnızca `03`'te; diğerleri "03'e uy" der.

---

## Çekirdek rule iskelet (00 örnek)

```markdown
---
alwaysApply: true
---

# <Proje> — Proje Kimliği

<1 paragraf kimlik>

## Tech Stack (Pin'li)

- …

Yeni framework/library → ADR gerekir.

## Monorepo Yapısı

\`\`\`
<≤12 satır ağaç>
\`\`\`

## Domain Terminolojisi

| Terim | Anlam |
| … |

## MVP Kapsamı Dışı

- …

---

Detay: `docs/00_PROJECT_OVERVIEW.md`
```

---

## Glob rule iskelet (10/14 örnek)

```markdown
---
description: <1 cümle>
globs:
  - "apps/api/**/*.ts"
---

# <Başlık>

<2 cümle context>

## <Pattern adı>

\`\`\`typescript
// ✓ Doğru
// ✗ Yanlış
\`\`\`

## Anti-pattern'ler

- …

---

Detay: `docs/04_BACKEND_SPEC.md` Bölüm X; `docs/03_API_CONTRACTS.md` Bölüm Y
```

---

## How-to iskelet (40 örnek)

```markdown
---
description: Step-by-step for <görev>. Use when <tetikleyici cümleler>.
---

# <Görev> Prosedürü

<N adım>. Her adım bir concern — atlama CI/review maliyeti.

## Step 1: …

`packages/...` veya `apps/...`

\`\`\`typescript
<minimal snippet>
\`\`\`

## Step 2: …

…

## Step N: Dokümantasyon

- [ ] `docs/03_API_CONTRACTS.md` … güncellendi

---

Detay: `docs/03_API_CONTRACTS.md`; `docs/07_SECURITY_IMPLEMENTATION.md`
```

---

## Phase rule — rules-architect yazmaz

Faz `.mdc` için `.cursor/skills/phase-creator/reference.md` iskeletini kullan. `rules-architect` yalnızca roadmap'ten **hangi fazların eksik olduğunu** listeler ve `phase-creator`'a devreder.

---

## Router (`CLAUDE.md`) içerik sınırları

| Bölüm | Max | İçerik |
| ----- | --- | ------ |
| Çalışma protokolü | ~25 satır | 5 adım: always → glob → how-to → faz → docs kazanır |
| alwaysApply özet | ~40 satır | 00–04 madde madde 1–2 cümle |
| Glob tablosu | ~20 satır | desen → NN dosya kısa ad |
| How-to tablosu | ~12 satır | görev → 40–47 |
| Faz tablosu | faz sayısına bağlı | NN → faz adı |
| docs indeks | ~8 satır | path listesi |

Router **asla** glob rule'ların pattern bölümünü kopyalamaz.

---

## Gap analizi checklist (mevcut proje)

```
[ ] 00–04 tam set var mı?
[ ] Her apps/* major path en az 1 glob kuralına bağlı mı?
[ ] Sık görevler (endpoint, ekran, migration) için 40–4x var mı?
[ ] CLAUDE.md router güncel mi (yeni .mdc satırda)?
[ ] alwaysApply toplamı ≤800 satır mı?
[ ] Spec duplikasyonu var mı? (rg uzun tablolar .mdc içinde)
[ ] Roadmap fazları ↔ 50+ .mdc birebir mi?
[ ] phase-creator docs-map minimum seti karşılanıyor mu?
```

---

## Lean Management referans indeks

Tam liste: `.cursor/rules/` (47 dosya). Özet:

| Katman | Dosyalar |
| ------ | -------- |
| 00–04 | identity, philosophy, naming, security, quality |
| 10–16 | backend arch, auth, permissions, processes, controllers, database, audit |
| 20–26 | FE arch, routes, forms, queries, components, a11y, design system |
| 30, 35 | terraform, testing |
| 40–47 | endpoint, screen, migration, permission, refactor, adr, fix-test, screen-catalog |
| 50–65 | phase 0–15 (+ 52.1) |

Yeni projede **en yakın komşu** dosyayı `Read` ile aç; ton ve detay seviyesini kopyala — içeriği docs'tan türet.

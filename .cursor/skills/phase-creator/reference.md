# Phase Document Reference — Lean Management

Bu dosya mevcut `.cursor/rules/*-phase-*.mdc` dosyalarından çıkarılmış **zorunlu yapı** ve **iterasyon kalıbı**dır. `phase-creator` skill'i **docs güncellemesi tamamlandıktan sonra** `.mdc` yazarken bunu kullanır.

## Docs ↔ .mdc ilişkisi

| Katman                            | Rol                                                                    |
| --------------------------------- | ---------------------------------------------------------------------- |
| `docs/01`–`10`, `06`, `adr/`      | **Tek doğruluk kaynağı** — spec, contract, ekran, roadmap              |
| `.cursor/rules/NN-phase-XX-*.mdc` | **Uygulama rehberi** — iterasyonlar, Stop, kısa scope; spec'e referans |

**Yazım sırası:** Önce [docs-map.md](docs-map.md) ile `docs/` güncelle → sonra `.mdc` (bu dosya).

**`.mdc`'de tekrarlanmaz:** Tam API body, ekran alan tablosu, DB kolon listesi → ilgili doc path + bölüm.

**`.mdc`'de kalır:** Goal özeti, iterasyon Hedef/Stop, Minimum bağlam (ör. `` `docs/03_API_CONTRACTS.md` Bölüm 9.7 ``), kısa dizin özeti, Done checklist, Explicit Don'ts.

## Dosya konumu ve adlandırma

| Parça  | Kural                               | Örnek                                  |
| ------ | ----------------------------------- | -------------------------------------- |
| Dizin  | `.cursor/rules/`                    | —                                      |
| Dosya  | `NN-phase-XX-<kebab-slug>.mdc`      | `56-phase-06-task-management.mdc`      |
| `NN`   | Sıra numarası (00, 50, 52, 56, 62…) | Roadmap ve mevcut dosyalarla çakışmama |
| `XX`   | Roadmap Faz numarası                | Faz 6 → `06`                           |
| Invoke | Chat'te `@NN-phase-XX-slug`         | `@56-phase-06-task-management`         |

**description** (YAML frontmatter, tek satır):

```yaml
description: '[Faz N] <özet> — <K> iterasyon/chat (<iter1 özeti> → <iter2> → …). Mesajda "Faz N — İterasyon M" belirt.'
```

Örnekler:

- `[Faz 2] DB + Auth foundation — 4 iterasyon/chat (Prisma → common+encryption → auth API → web+E2E).`
- `[Faz 12] Untitled UI geçişi — 5 iterasyon/chat (altyapı → base → shell → ekran dalga 1 → dalga 2 + temizlik).`

---

## Bölüm sırası (standart iskelet)

````markdown
---
description: '...'
---

# Faz N: <Başlık>

## Goal

<1–3 paragraf: faz sonunda ne tamamlanmış olacak>

## Feature branch (zorunlu)

Faz koduna **main üzerinde başlanmaz**. İlk commit/dosya değişikliği öncesi `48-git-phase-branch.mdc` uygula.

**Bu faz branch adı:** `feat/phase-<XX>-<slug>` — `<XX>` ve `<slug>` dosya adından (`NN-phase-XX-<slug>.mdc`).

**Stop (İterasyon 1, kod öncesi):** [ ] `main` güncel; [ ] faz branch oluşturuldu; [ ] `git push -u origin HEAD`.

## Bu fazın çalışma modeli (iterasyonlar)

<"Tek sohbette tamamlanmaz" + @dosya + "Faz N — İterasyon M" kuralı>

---

### İterasyon 1 — <Kısa ad>

**Hedef:** <ölçülebilir tek cümle>

**Yapılacaklar:** (veya madde listesi)

1. …

**Minimum bağlam:** `docs/...` path listesi

**Bu iterasyonda yok:** <scope creep önleme>

**Stop:** [ ] … [ ] … PR/onay.

---

### İterasyon 2 — …

(repeat)

## Required Context

- `docs/...` — **path + bölüm** (Adım 4'te güncellenen sürüm)
- Auto-attached: ilgili rule numaraları (varsa)

Örnek (referans stili — kopyala, içeriği docs'tan türet):

```markdown
## Required Context

- `docs/01_DOMAIN_MODEL.md` Bölüm 5 (Task state machine, claim modes)
- `docs/03_API_CONTRACTS.md` Bölüm 9.7 (Tasks)
- `docs/06_SCREEN_CATALOG.md` — S-TASK-LIST, S-TASK-DETAIL, S-MY-TASKS
```
````

## Scope

### Backend — Files to create

(tree veya liste)

### Frontend — Files to create

(tree veya liste)

### Files NOT touched

- … (sonraki fazlara bırakılanlar)

## Constraints

### Use

- …

### Avoid

- …

## Done Definition

### Backend

- [ ] …

### Frontend

- [ ] …

### Manual smoke test (opsiyonel)

```bash
# …
```

## Explicit Don'ts

- …

## Kısıtlar & Riskler (opsiyonel tablo)

| Risk | Önlem |

## Related ADRs (varsa)

- ADR-…

## Sonraki fazlarla ilişki (opsiyonel)

…

---

Phase done → `docs/10_IMPLEMENTATION_ROADMAP.md` Faz N check mark.

```

Kısa fazlarda (2 iterasyon) **Scope** ağaçları kısaltılabilir; **Goal**, **iterasyonlar**, **Done Definition**, **Explicit Don'ts** zorunlu kalır.

---

## İterasyon tasarım ilkeleri

| İlke | Uygulama |
|------|----------|
| 1 chat ≈ 1 PR | Her iterasyon bağımsız merge edilebilir |
| Hedef önce | `**Hedef:**` her zaman ilk satır |
| Faz branch | Goal ile iterasyonlar arasında **Feature branch (zorunlu)** — `48-git-phase-branch.mdc` |
| Scope sınırı | `**Bu iterasyonda yok:**` zorunlu |
| Doğrulama | `**Stop:**` checklist + test komutu |
| Bağlam | `**Minimum bağlam:**` gerçek doc path |
| Boyut | Tipik 2–5 iterasyon; 6+ ancak net alt-dalga varsa (ör. UI migrasyon dalgaları) |
| Sıra | Altyapı → domain API → UI → temizlik/E2E (genel pattern; dikey dilim istisna belirtilir) |

### İterasyon isimlendirme

- `### İterasyon N — <2–5 kelime>` (Türkçe veya TR+EN terim)
- Örnek: `### İterasyon 3 — Shell Migrasyonu`

### Stop satırı kalıbı

```

**Stop:** [ ] <doğrulama 1>; [ ] <doğrulama 2>; PR/onay → İterasyon N+1.

````

Son iterasyon: `**Stop:** Faz N Done Definition; roadmap işareti.`

---

## İterasyon içeriği — iyi vs kötü

**İyi (yutulabilir):**

```markdown
### İterasyon 2 — Auth API

**Hedef:** 8 auth endpoint + 3 guard; integration test login→refresh→logout.

**Minimum bağlam:** `docs/03_API_CONTRACTS.md` Bölüm 9.1; `docs/07_SECURITY_IMPLEMENTATION.md` Bölüm 2–3.

**Scope:** `apps/api/src/auth/**` + `app.module` guard register. **Frontend yok.**

**Doğrulama:** Service coverage ≥90%; integration test yeşil.

**Stop:** [ ] curl smoke; [ ] integration yeşil. PR/onay.
````

**Kötü (çok büyük / belirsiz):**

```markdown
### İterasyon 1 — Her şey

Backend, frontend, testler, refactor, performans.
```

---

## Katman ipuçları (araştırmadan sonra seç)

| Faz tipi           | Tipik iterasyon dizisi                                      |
| ------------------ | ----------------------------------------------------------- |
| Altyapı / scaffold | omurga → uygulamalar+CI                                     |
| Domain API         | schema/service → endpoint → integration                     |
| Full-stack feature | API → UI → E2E                                              |
| UI migrasyon       | altyapı → base components → shell → ekran dalga 1 → dalga 2 |
| Admin              | settings API → UI → crons/dashboard                         |

---

## Mevcut faz dosyaları (referans indeks)

| Dosya                                | Faz | İterasyon sayısı |
| ------------------------------------ | --- | ---------------- |
| `50-phase-00-monorepo-scaffold.mdc`  | 0   | 2                |
| `51-phase-01-infrastructure.mdc`     | 1   | 4                |
| `52-phase-02-auth-foundation.mdc`    | 2   | 4                |
| `52.1-phase-02-GoogleSSOAuth.mdc`    | 2.1 | 4                |
| `53-phase-03-users-roles.mdc`        | 3   | 3                |
| `54-phase-04-permission-system.mdc`  | 4   | 3                |
| `55-phase-05-process-engine.mdc`     | 5   | 4                |
| `56-phase-06-task-management.mdc`    | 6   | 2                |
| `57-phase-07-notifications.mdc`      | 7   | 3                |
| `58-phase-08-admin-panel.mdc`        | 8   | 3                |
| `59-phase-09-dashboard-polish.mdc`   | 9   | 2                |
| `60-phase-10-performance.mdc`        | 10  | 4                |
| `61-phase-11-security-hardening.mdc` | 11  | 4                |
| `62-phase-12-UI-migration.mdc`       | 12  | 5                |

Yeni faz yazarken **en yakın komşu** fazı `Read` ile aç; ton ve detay seviyesini kopyala.

---

## Roadmap ile hizalama

- Faz numarası `docs/10_IMPLEMENTATION_ROADMAP.md` ile tutarlı olmalı.
- Alt-faz (2.1 gibi) için `52.1-phase-02-...` pattern'i kullanılabilir.
- Roadmap faz detayı **Adım 4 (docs)** içinde güncellenir; `.mdc` sonunda yalnızca işaretleme notu.

## Ek kaynak

- Hangi `docs/` dosyası ne zaman: [docs-map.md](docs-map.md)

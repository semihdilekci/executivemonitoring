# Phase Document Reference — YGIP

`.cursor/rules/NN-phase-XX-*.mdc` dosyalarının **zorunlu yapısı** ve **iterasyon kalıbı**. `phase-creator` skill'i: önce `Docs/` günceller → sonra bu referans + [iteration-blueprint.md](iteration-blueprint.md) ile `.mdc` yazar.

## Docs ↔ .mdc ilişkisi

| Katman | Rol |
| ------ | --- |
| `Docs/01`–`10`, `06`, `mimari-kararlar.md` | **Tek doğruluk kaynağı** — spec, contract, ekran, roadmap |
| `.cursor/rules/NN-phase-XX-*.mdc` | **Uygulama rehberi** — plan-modu kalitesinde iterasyonlar; spec'e pointer |

**Yazım sırası:** [docs-map.md](docs-map.md) ile `Docs/` güncelle → `.mdc` (bu dosya + iteration-blueprint).

| `.mdc`'de **kalmaz** (yalnızca Docs'ta) | `.mdc`'de **kalır** (iterasyon başına) |
| --------------------------------------- | -------------------------------------- |
| Tam API body, response örneği | Docs § referansı + uygulama notu |
| Ekran alan tablosu, UX state detayı | `S-*` ID listesi + hangi § okunacak |
| DB kolon listesi | Tablo adı + migration dosya adı + `Docs/02` § |
| 50+ satırlık dosya ağacı | İterasyon **Dosya kapsamı** tablosu (≤12 satır) |

---

## Dosya konumu ve adlandırma

| Parça | Kural | Örnek |
| ----- | ----- | ----- |
| Dizin | `.cursor/rules/` | — |
| Dosya | `NN-phase-XX-<kebab-slug>.mdc` | `51-phase-01-backend-core.mdc` |
| `NN` | Sıra (50–58 MVP-0); çakışma yok | `Glob *-phase-*.mdc` |
| `XX` | Roadmap faz no | Faz 1 → `01` |
| Invoke | `@NN-phase-XX-slug` + `Faz N — İterasyon M` | `@51-phase-01-backend-core` |

**description** (YAML frontmatter):

```yaml
description: '[Faz N] <özet> — <K> iterasyon/chat (<iter1> → <iter2> → …). Mesajda "Faz N — İterasyon M" belirt.'
```

---

## Faz dosyası iskeleti (üst seviye)

````markdown
---
description: '...'
---

# Faz N: <Başlık>

## Goal
<1–3 cümle; detay `Docs/10` Faz N>

## Feature branch (zorunlu)
<`48-git-phase-branch.mdc`; branch adı; İterasyon 1 öncesi Stop>

## Bu fazın çalışma modeli
- Tek sohbet fazı bitirmez
- Her chat: `@NN-phase-XX-slug` + **「Faz N — İterasyon M」**
- Agent **yalnızca o iterasyonun Docs okuma sırasını** okur; tüm spec değil
- Plan moduna geçme — iterasyon blueprint yeterli

---

### İterasyon 1 — …
<iteration-blueprint.md iskeletinin tamamı>

### İterasyon 2 — …
…

## Required Context
- `Docs/...` §… — faz geneli (iterasyon listesi için `Docs/10` Faz N)

## Done Definition
- [ ] Ölçülebilir maddeler; `S-*` / endpoint ID ile

## Explicit Don'ts
- MVP dışı + `Docs/00` uyumu

---

Phase done → `Docs/10_IMPLEMENTATION_ROADMAP.md` Faz N işareti.
````

**İterasyon detayı:** [iteration-blueprint.md](iteration-blueprint.md) — her iterasyon için zorunlu 9 bölüm.

---

## İterasyon tasarım ilkeleri

| İlke | Uygulama |
| ---- | -------- |
| Plan modu yerine geçer | Uygulama planı + Spec→kod + Stop; agent tekrar planlamaz |
| Context window | 1 chat ≈ 1 PR; ≤12 dosya; Docs okuma ≤5 dosya/iterasyon |
| Docs pointer | Her adım `Docs/X` §Y ile bağlı; belirsiz "spec'e bak" yok |
| Hedef önce | `**Hedef:**` ölçülebilir tek cümle |
| Scope duvarı | `**Bu iterasyonda yok:**` + Dosya kapsamı "Dokunma" |
| Doğrulama | Stop'ta çalıştırılabilir `pytest`/`ruff`/smoke komutu |
| Boyut | Tipik 4–8 iterasyon; 9+ ancak net alt-dalga (UI dalgaları) |
| Sıra | Altyapı → domain/DB → API → UI → entegrasyon |

### Stop kalıbı

```
**Stop:**
- [ ] <komut veya smoke>
- [ ] <test>
- [ ] PR/onay → İterasyon N+1
```

---

## İyi vs kötü iterasyon

**İyi** — uygulama hazır, context sınırlı:

```markdown
### İterasyon 3 — Auth Endpoints (1.3)

**Hedef:** Login/refresh/logout + integration test yeşil.

**Docs okuma sırası:**
1. `Docs/10_IMPLEMENTATION_ROADMAP.md` §1.3
2. `Docs/03_API_CONTRACTS.md` §2
3. `Docs/07_SECURITY_IMPLEMENTATION.md` §2–3

**Uygulama planı:**
1. `schemas/auth.py` — `Docs/03` §2.1 alanları
2. `routers/auth.py` — üç endpoint + rate limit
3. `tests/integration/test_auth_flow.py`

**Dosya kapsamı:** … (tablo)
**Spec → kod eşlemesi:** … (≥3 satır)
**Stop:** [ ] `pytest tests/integration/test_auth_flow.py -v`
```

**Kötü** — plan modu gerekir, context belirsiz:

```markdown
### İterasyon 1 — Backend

**Hedef:** Auth ve user API.
**Minimum bağlam:** Docs/03, Docs/04
**Stop:** Testler yeşil.
```

---

## Katman ipuçları (iterasyon dizisi)

| Faz tipi | Tipik iterasyon dizisi |
| -------- | ---------------------- |
| Altyapı | scaffold → CI → migration dalgaları → IaC |
| Backend API | app iskelet → security util → endpoint grubu → audit → seed |
| Collector/worker | BaseCollector → tek kaynak tipi → orchestration |
| Frontend | route+layout → data hook → ekran → admin sayfası |
| Full-stack | API iterasyonu → UI iterasyonu (karıştırma) |

---

## Mevcut MVP-0 faz dosyaları

| Dosya | Faz | İterasyon |
| ----- | --- | --------- |
| `50-phase-00-infra-scaffold.mdc` | 0 | 6 |
| `51-phase-01-backend-core.mdc` | 1 | 8 |
| `52-phase-02-collectors.mdc` | 2 | 6 |
| `53-phase-03-processor.mdc` | 3 | 6 |
| `54-phase-04-ai-engine.mdc` | 4 | 8 |
| `55-phase-05-notifications.mdc` | 5 | 5 |
| `56-phase-06-web-frontend.mdc` | 6 | 9 |
| `57-phase-07-mobile.mdc` | 7 | 4 |
| `58-phase-08-pipeline-runtime.mdc` | 8 | 6 |

Yeni faz yazarken komşu fazı `Read` ile aç; **iterasyon detay seviyesi** için [iteration-blueprint.md](iteration-blueprint.md) esas alınır (eski kısa iterasyonlar yeniden üretimde yükseltilir).

---

## Roadmap hizalama

- Faz no ↔ `Docs/10_IMPLEMENTATION_ROADMAP.md`
- Roadmap faz detayı **Adım 4 (Docs)** içinde; `.mdc` iterasyonları `§N.M` ile roadmap alt maddelerine hizalanır
- Ek kaynak: [docs-map.md](docs-map.md)

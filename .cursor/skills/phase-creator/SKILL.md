---
name: phase-creator
description: Researches the Lean Management monorepo, asks scope questions one at a time, updates docs/ consistently after approval, then drafts .cursor/rules phase .mdc files that reference docs as single source of truth. Use for new implementation phases, faz dokümanı, phase rule, roadmap slice, or phase_creator / yeni faz planla.
---

# Phase Creator

> **Cursor:** Proje skill'i — `.cursor/skills/phase-creator/`. Claude Code eşdeğeri: `.claude/skills/phase-creator/`. İçerik değişince **her iki kopyayı** senkron tut.
>
> **Önkoşul:** Çekirdek/glob/how-to `.mdc` paketi yoksa önce **`rules-architect`** skill'i; faz `.mdc` bu skill'in kapsamındadır.
>
> **Implementasyon sonrası:** Gap audit için **`phase-controller`** skill'i — fix raporu + `-fix.mdc` (kod değiştirmez).

Kullanıcının kapsamı için **araştırır** → **tek tek sorular** → **taslak + docs etki planı** → **onay** → **`docs/` güncellemesi** → **`.mdc` (docs referanslı)**. Onay ve kod yazımı öncesi sıra değişmez.

## Zorunlu kurallar

1. **Tek soru kuralı:** Her turda yalnızca **bir** soru. Anket / numaralı soru listesi yasak.
2. **Onay kapısı (taslak):** Kullanıcı onaylamadan ne `docs/` ne `.mdc` yazılır.
3. **Docs önce:** Onay sonrası sıra: **(A) `docs/` güncelle** → **(B) `.mdc` yaz**. `.mdc`, güncellenmiş `docs/` referanslarına dayanır.
4. **Tek doğruluk kaynağı:** Spec detayı `docs/` içinde; `.mdc` tekrar etmez — path + bölüm referansı. Harita: [docs-map.md](docs-map.md).
5. **Araştırma önce:** İlk sorudan önce roadmap, ilgili `docs/`, faz `.mdc` örnekleri, kod taraması.
6. **Yutulabilir iterasyonlar:** Her iterasyon tek PR/chat; net Hedef, Bu iterasyonda yok, Stop.
7. **MVP disiplini:** Kapsam dışı roadmap Wave ile işaretlenir; faza eklenmez.
8. **Faz feature branch (zorunlu):** Her faz `.mdc` **Feature branch (zorunlu)** bölümü içerir; `feat/phase-<XX>-<slug>` adı dosya adından türetilir. Agent kod/commit öncesi `48-git-phase-branch.mdc` uygular — main'de faz kodu yasak.

## Akış özeti

```
[1 Araştırma] → [2 Soru döngüsü] → [3 Taslak + docs planı] → [4 Onay]
    → [5 docs/ güncelle] → [6 Özet] → [7 .mdc yazımı] → [8 Doğrulama]
```

---

## Adım 1 — Araştırma

| Kaynak                              | Ne için                                   |
| ----------------------------------- | ----------------------------------------- |
| `docs/10_IMPLEMENTATION_ROADMAP.md` | Faz no, bağımlılık, Bölüm 9 yaşam döngüsü |
| `.cursor/rules/*-phase-*.mdc`       | En yakın 1–2 örnek                        |
| `docs/01`–`08`, `06_SCREEN_CATALOG` | Mevcut spec                               |
| `rg` / `SemanticSearch`             | Kod vs doküman boşluğu                    |

Çıktı: kısa bulgular + **ilk tek soru** (Goal / katman / bağımlılık önceliği).

---

## Adım 2 — Soru döngüsü

Her tur:

```markdown
**Anladıklarım:** …
**Öneri (varsa):** …
**Soru:** …?
```

Kategoriler (tek tek): Goal → katman → bağımlılık → iterasyon sırası → test/Done → risk → faz numarası.

Yeterlilik: Goal, katmanlar, iterasyon sayısı, Done, Explicit Don'ts, **hangi docs dosyalarının etkileneceği** kabaca net → Adım 3.

---

## Adım 3 — Taslak öneri (onay öncesi)

`.mdc` ve `docs/` **yazma**. Sun:

```markdown
## Önerilen faz taslağı

**Önerilen dosya:** `.cursor/rules/NN-phase-XX-<slug>.mdc`
**Description:** [Faz N] … — K iterasyon/chat (…).

### Goal

…

### İterasyon özeti

| #   | Hedef | Stop |
| --- | ----- | ---- |
| 1   | …     | …    |

### MVP dışı

- …

### Done Definition (özet)

- …

### Planlanan docs güncellemeleri

| Dosya                               | Bölüm / ekleme | Neden |
| ----------------------------------- | -------------- | ----- |
| `docs/10_IMPLEMENTATION_ROADMAP.md` | Faz N detayı   | …     |
| `docs/03_API_CONTRACTS.md`          | …              | …     |
| …                                   | …              | …     |

**Dokunulmayacak docs:** …

Bu taslağı ve docs planını onaylıyor musun? Onaydan sonra önce docs güncellemelerini uygulayacağım, ardından .mdc dosyasını yazacağım.
```

Düzeltme → taslağı güncelle → tekrar onay iste.

---

## Adım 4 — Onay sonrası: `docs/` güncellemesi

Kullanıcı onayladıktan sonra **yalnızca** Adım 4; `.mdc` henüz yok.

### 4.1 Hazırlık

1. [docs-map.md](docs-map.md) — faz tipine göre minimum dosya seti.
2. Taslaktaki tabloyu checklist yap; her dosyayı `Read` + `Grep` ile doğru bölümü bul.
3. Mevcut bölüm yapısını kopyala (Screen Catalog `S-KTI-*` → yeni `S-*`; API'de benzer endpoint bloğu).

### 4.2 Yazım kuralları

- Türkçe user-facing metin; identifier İngilizce (`02-language-naming`).
- Uydurma path/ekran ID yok — önce `rg` ile doğrula.
- `10_IMPLEMENTATION_ROADMAP`: `### Faz N — …` + hedef, bağımlılık, iterasyon özeti (kod değil, plan).
- Yeni mimari karar → `docs/adr/00NN-*.md` (`.cursor/rules/45-write-adr.mdc`).
- Süreç tipi → `docs/processes/<slug>.md` (+ 01, 02, 03, 05, 06).

### 4.3 Tutarlılık kontrolü

Güncelleme sonrası çapraz kontrol:

- [ ] Enum/permission/route üç dosyada aynı (`02` / `03` / `06`)
- [ ] Roadmap faz no ↔ taslak faz no
- [ ] MVP dışı maddeler `00` veya roadmap Post-MVP ile uyumlu
- [ ] Screen ID benzersiz

### 4.4 Kullanıcıya özet (docs tamamlandı)

```markdown
## docs/ güncellemeleri tamamlandı

| Dosya | Değişiklik |
| ----- | ---------- |
| …     | …          |

Sonraki adım: `.cursor/rules/NN-phase-XX-<slug>.mdc` yazımı. Devam edeyim mi?
```

İkinci onay iste (kısa). Kullanıcı "devam" / onay verince Adım 5. Büyük sapma varsa önce düzelt.

**Bu adımda yok:** Uygulama kodu; `.mdc` dosyası.

---

## Adım 5 — Faz `.mdc` yazımı (docs referanslı)

Güncel `docs/` tek doğruluk kaynağı. [reference.md](reference.md) iskeleti.

### Referans-first kurallar

| `.mdc` bölümü                      | İçerik                                                        |
| ---------------------------------- | ------------------------------------------------------------- |
| **Goal**                           | 1–3 cümle; detay `docs/10` Faz N                              |
| **Feature branch (zorunlu)**       | `feat/phase-<XX>-<slug>` tam adı; `48-git-phase-branch.mdc` referansı; İterasyon 1 Stop checklist |
| **Required Context**               | `docs/…` path + **Bölüm adı/numarası** listesi                |
| **Her iterasyon — Minimum bağlam** | O iterasyonda okunacak doc path'leri                          |
| **Scope**                          | Kısa modül/dizin listesi; tam spec docs'ta                    |
| **Done Definition**                | Ölçülebilir checklist; ekran/API maddeleri `06` / `03` ID ile |
| **Explicit Don'ts**                | MVP dışı + `docs/00` ile uyumlu                               |

**Yasak:** `03`/`06`'daki tam tabloları `.mdc`'ye kopyalamak; 50+ satırlık dosya ağacı (özet ≤15 satır veya "bkz. `docs/04` Bölüm X").

### Yazım adımları

1. `Glob .cursor/rules/*-phase-*.mdc` — `NN` / faz no çakışması yok.
2. Frontmatter `description`: `[Faz N] … — K iterasyon/chat (…). Mesajda "Faz N — İterasyon M" belirt.`
3. İterasyonlar: Hedef, Yapılacaklar (kısa), Minimum bağlam (**güncel doc path**), Bu iterasyonda yok, Stop.
4. **Feature branch:** Goal ile iterasyonlar arasına `## Feature branch (zorunlu)` — tam branch adı + `48-git-phase-branch.mdc` + İterasyon 1 öncesi Stop checklist.
5. Çalışma modeli: tek sohbet bitmez + `@NN-phase-XX-slug` + iterasyon etiketi + branch açmadan kod yok.
6. Son satır: `Phase done → docs/10_IMPLEMENTATION_ROADMAP.md Faz N işareti` (roadmap maddesini Adım 4'te zaten eklediysen tekrarlama).

Çıktı: dosya yolu, iterasyon sayısı, ilk chat etiketi (`Faz N — İterasyon 1`).

---

## Adım 6 — Doğrulama

**docs/**

- [ ] Taslaktaki her satır uygulandı veya gerekçeli atlandı
- [ ] docs-map minimum seti karşılandı
- [ ] Çapraz referanslar tutarlı

**.mdc**

- [ ] Required Context / Minimum bağlam gerçek path + bölüm
- [ ] Spec tekrarı yok; referans var
- [ ] Her iterasyon Hedef ölçülebilir; Bu iterasyonda yok dolu
- [ ] **Feature branch (zorunlu)** bölümü + `feat/phase-...` adı mevcut
- [ ] Stop: test/lint/PR onayı; İterasyon 1 Stop'ta branch push checklist
- [ ] 1 chat ≈ 1 PR boyutu

---

## Örnek taslak parçası (docs planı)

| Dosya                                | Bölüm               | Neden             |
| ------------------------------------ | ------------------- | ----------------- |
| `docs/03_API_CONTRACTS.md`           | 9.x Impersonation   | Yeni endpoint'ler |
| `docs/06_SCREEN_CATALOG.md`          | S-IMPERSONATION-\*  | Admin UI          |
| `docs/07_SECURITY_IMPLEMENTATION.md` | Impersonation audit | Actor ayrımı      |
| `docs/10_IMPLEMENTATION_ROADMAP.md`  | Faz 13 detay        | Plan              |

---

## Ek kaynaklar

- [reference.md](reference.md) — `.mdc` iskeleti
- [docs-map.md](docs-map.md) — hangi doc ne zaman
- `.cursor/skills/add-process-type/SKILL.md` — süreç tipi docs kalıbı (Phase 1)
- `docs/10_IMPLEMENTATION_ROADMAP.md` Bölüm 9 — yaşam döngüsü

## Anti-pattern'ler

- ❌ Onaysız `docs/` veya `.mdc` yazmak
- ❌ `.mdc` önce, `docs/` sonra
- ❌ `.mdc` içinde API/ekran spec duplikasyonu
- ❌ Tek mesajda çoklu soru
- ❌ Var olmayan `S-*` / endpoint / bölüm uydurmak
- ❌ `~/.cursor/skills-cursor/` altına dosya
- ❌ Yalnızca `.cursor/` veya yalnızca `.claude/` kopyasını güncelleyip diğerini unutmak

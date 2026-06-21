---
name: rules-architect
description: Analyzes docs/ to understand a project, designs a layered .cursor/rules/*.mdc architecture (alwaysApply, globs, agent-requestable), writes rules that reference docs as single source of truth without duplicating spec, creates CLAUDE.md router, then delegates phase .mdc files to phase-creator from docs/10_IMPLEMENTATION_ROADMAP. Use when bootstrapping cursor rules, rules-architect, .mdc paketi, kural mimarisi, docs'tan rules üret, or after docs/ is ready but .cursor/rules/ is empty or incomplete.
disable-model-invocation: true
---

# Rules Architect

> **Cursor:** `.cursor/skills/rules-architect/`. Claude Code eşdeğeri: `.claude/skills/rules-architect/`. İçerik değişince **her iki kopyayı** senkron tut.

`docs/` hazır → **katmanlı `.mdc` mimarisi tasarla** → onay → kuralları yaz → router (`CLAUDE.md`) → roadmap fazları için **`phase-creator`** devret.

**Referans implementasyon:** Lean Management (`.cursor/rules/` — 47 dosya, 4 katman). Detay: [layer-taxonomy.md](layer-taxonomy.md), [reference.md](reference.md).

## Zorunlu kurallar

1. **Docs önce, rules sonra:** Spec `docs/` içinde kalır; `.mdc` path + bölüm referansı verir — tam tablo/API body/kolon listesi kopyalanmaz.
2. **Onay kapısı:** Mimari taslak + dosya listesi onaylanmadan `.mdc` yazılmaz.
3. **Tek soru kuralı:** Keşif ve tasarım turunda her mesajda yalnızca **bir** soru.
4. **Katman disiplini:** Her kural tam olarak bir katmana aittir (alwaysApply / glob / how-to / phase). Karıştırma yasak.
5. **Context bütçesi:** alwaysApply toplamı hedef ≤800 satır; glob kuralı ≤400 satır (istisna gerekçeli); how-to ≤350 satır.
6. **Faz kuralları:** `50+-phase-*.mdc` dosyaları bu skill'in **Faz B** adımında değil — **`phase-creator`** skill'i ile üretilir (docs roadmap güncel olmalı).

## Akış özeti

```
[A Docs keşfi] → [B Mimari taslak] → [C Onay]
    → [D Çekirdek 00–04] → [E Glob 10–3x] → [F How-to 40–4x] → [G Router CLAUDE.md]
    → [H Roadmap fazları → phase-creator devri]
```

---

## Adım A — Docs keşfi

### A.1 Envanter

| Kaynak | Ne çıkarılır |
| ------ | ------------ |
| `docs/00_*` … `docs/10_*` | Kapsam, domain, stack, API, ekran, güvenlik, test, workflow, roadmap |
| `docs/adr/`, `docs/mimari-kararlar.md` | Sabit kararlar, stack pin |
| `docs/processes/`, `docs/lean-design-system/` | Domain/UI alt spec |
| Repo yapısı (`apps/`, `packages/`, `infrastructure/`) | Glob desenleri |
| Mevcut `.cursor/rules/` (varsa) | Boşluk / duplikasyon |

`Glob docs/**/*.md` + her numaralı doc'un **içindekiler / başlık** taraması. Tam okuma: `00`, `09`, `10` + stack/domain özeti için `04`/`05`/`07`/`08` özet bölümleri.

### A.2 Çıktı (kullanıcıya)

```markdown
## Docs özeti

**Proje:** …
**Stack (pin'li):** …
**Domain terimleri:** …
**Docs envanteri:** | Dosya | Rol | Durum (tam/kısmi/eksik) |
**Docs → rules ihtiyacı:** hangi concern docs'ta var, hangi katmanda rule gerekir
**İlk boşluk:** …

**Soru:** …? (tek soru — örn. MVP kapsamı net mi, yoksa 00'ı önce tamamlayalım mı?)
```

Docs yetersizse rule yazma — eksik doc listesi öner, onay bekle.

---

## Adım B — Mimari taslak (onay öncesi)

`.mdc` **yazma**. Sun:

```markdown
## Önerilen rules mimarisi

### Katman tablosu

| Katman | Numara | Tetikleme | Tahmini dosya | Satır bütçesi |
| ------ | ------ | --------- | ------------- | ------------- |
| Çekirdek | 00–04 | alwaysApply | 5 | ~150/dosya |
| Domain glob | 10–16 BE, 20–26 FE, 30 infra, 35 test | globs | N | ~250–350 |
| How-to | 40–47 | description (agent-requestable) | M | ~200–330 |
| Faz | 50+ | description + `@NN-phase-*` | roadmap'ten | phase-creator |

### Dosya listesi (taslak)

| Dosya | Katman | alwaysApply / globs / desc | docs referansları | Tahmini satır |
| … | … | … | … | … |

### Router

- `CLAUDE.md` (veya `AGENTS.md`): glob yönlendirme tablosu + how-to indeks + faz indeks — **kuralları tekrar etmez**

### Context bütçesi tahmini

- alwaysApply oturum başı: ~X satır
- Tipik backend edit: +Y satır (hangi glob'lar)
- Tipik yeni endpoint görevi: agent `40-add-new-endpoint` requestable

### MVP dışı / yazılmayacak kurallar

- …

### Faz planı (phase-creator devri)

| Faz | Önerilen .mdc | phase-creator hazır mı (roadmap doc) |
| … | … | … |

Bu mimariyi onaylıyor musun? Onaydan sonra sıra: 00–04 → glob → how-to → router.
```

Düzeltme → taslağı güncelle → tekrar onay.

Detaylı numaralandırma ve frontmatter: [layer-taxonomy.md](layer-taxonomy.md).

---

## Adım C — Onay sonrası: kural yazımı

Sıra değişmez. Her dosya yazıldıktan sonra checklist (aşağı).

### D — Çekirdek (00–04)

| NN | Tipik içerik | docs kaynağı |
| -- | ------------ | ------------ |
| 00 | Kimlik, stack pin, monorepo, domain terimleri, MVP dışı | `00`, `01` özet, ADR stack |
| 01 | Vibe coding, MVP scope, test-first, self-review | `10` Bölüm 1, `09` |
| 02 | TR/EN hibrit naming, commit, error code | `09` Bölüm 3 |
| 03 | Güvenlik 6'lı checklist (executable) | `07` özet |
| 04 | Coverage, CI gate, bundle, a11y eşik | `08`, `09`, `04` kalite |

**İçerik kuralı:** Distille edilmiş prensip + 1–2 minimal kod örneği. Uzun spec → `Detay: docs/XX …` footer.

Frontmatter: yalnızca `alwaysApply: true` (description opsiyonel, kısa).

### E — Domain glob (10–3x)

Her dosya:

```yaml
---
description: <1 cümle — rule picker>
globs:
  - "<glob1>"
  - "<glob2>"  # gerekirse
---
```

İçerik: **pattern + convention + anti-pattern**. Spec tablosu yok → `docs/03` Bölüm X referansı.

Glob dar tutulur — geniş glob + uzun dosya = context şişmesi.

### F — How-to (40–4x)

Frontmatter: yalnızca `description` (trigger terimleri İngilizce, WHAT + WHEN). **globs yok**, **alwaysApply yok**.

Adım adım prosedür; her adım ilgili doc path'e link.

Tipik set: endpoint, ekran, migration, permission, refactor, ADR, failing test (+ projeye özel 47.x).

Kalıp: [reference.md](reference.md) § How-to iskelet.

### G — Router (`CLAUDE.md`)

Şablon: [router-template.md](router-template.md).

- alwaysApply 00–04 **özet** (5–8 madde each, tam metin değil)
- Glob yönlendirme tablosu
- How-to yönlendirme tablosu
- Faz yönlendirme tablosu (`.mdc` path kısa ad)
- `docs/` indeks + "docs kazanır" kuralı
- "49 kuralın tamamını okuma" verimlilik notu

---

## Adım H — Faz kuralları (phase-creator devri)

Core + glob + how-to + router bittikten sonra:

1. `docs/10_IMPLEMENTATION_ROADMAP.md` faz listesini oku.
2. Kullanıcıya özet: hangi fazların `.mdc`'si var / eksik.
3. Eksik veya yeni faz için **`phase-creator` skill'ini uygula** — o skill'in akışı (docs güncelle → faz `.mdc`) aynen geçerli.
4. `rules-architect` faz `.mdc` içeriğini **doğrudan yazmaz** (duplikasyon ve sıra hatası önleme).

Kullanıcıya:

```markdown
## Core rules tamamlandı

| Yazılan | Adet |
| … | … |

**Sonraki adım:** Faz N için `@phase-creator` ile devam edelim mi? (Roadmap'te Faz N …)

**Implementasyon sonrası:** `@phase-controller` ile gap audit → `Docs/fix-reports/` + `-fix.mdc`.
```

---

## Dosya başına doğrulama checklist

- [ ] Tek katman (alwaysApply XOR globs XOR description-only)
- [ ] Spec duplikasyonu yok — path + bölüm referansı var
- [ ] Satır bütçesi içinde veya gerekçeli istisna
- [ ] Frontmatter geçerli YAML
- [ ] Numara çakışması yok (`Glob .cursor/rules/*.mdc`)
- [ ] Router tablosunda satır var
- [ ] docs ile çelişki yok (çelişki → docs güncelle öner, rule'da uydurma)

---

## Yeni proje vs mevcut proje

| Durum | Davranış |
| ----- | -------- |
| `.cursor/rules/` boş, `docs/` dolu | Tam akış A→H |
| Kısmi rules var | Gap analizi; yalnızca eksik katman/dosya; numara çakışması kontrol |
| `docs/` eksik | Rule yazma dur; önce doc tamamlama listesi |
| Sadece faz `.mdc` isteniyor | Doğrudan `phase-creator`; bu skill atlanır |

---

## Anti-pattern'ler

- ❌ Onaysız `.mdc` yazmak
- ❌ API/ekran/DB spec'ini rule'a kopyalamak
- ❌ Her şeyi `alwaysApply: true` yapmak
- ❌ Tek dev `.mdc` (1000+ satır monolith)
- ❌ Glob'suz domain kuralı (her oturumda yüklenir)
- ❌ Router'da kuralların tam metnini tekrarlamak
- ❌ Faz `.mdc`'yi phase-creator atlayarak yazmak
- ❌ `~/.cursor/skills-cursor/` altına dosya

## Ek kaynaklar

- [layer-taxonomy.md](layer-taxonomy.md) — 4 katman, numaralandırma, bütçe
- [reference.md](reference.md) — docs↔rules haritası, iskeletler
- [router-template.md](router-template.md) — CLAUDE.md şablonu
- `.cursor/skills/phase-creator/SKILL.md` — faz `.mdc` üretimi

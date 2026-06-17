---
name: phase-creator
description: Researches YGIP monorepo scope, updates Docs/ as single source of truth, then writes .cursor/rules phase .mdc files with plan-mode-quality iterations—granular per-chat work, Docs/ section pointers, implementation-ready steps without re-planning. Use for faz dokümanı, phase rule, roadmap slice, yeni faz planla, or improving phase iteration detail.
---

# Phase Creator

> **Cursor:** `.cursor/skills/phase-creator/`. Claude Code: `.claude/skills/phase-creator/` — senkron tut.
>
> **Önkoşul:** Çekirdek `.mdc` yoksa **`rules-architect`**; faz `.mdc` bu skill'de.
>
> **Implementasyon sonrası:** **`phase-controller`** — gap audit (kod değiştirmez).

Araştır → tek soru → taslak + docs planı → onay → **`Docs/` güncelle** → **`.mdc` (plan-modu kalitesinde iterasyonlar)**.

## Zorunlu kurallar

1. **Tek soru:** Tur başına bir soru; anket yasak.
2. **Onay kapısı:** Onaysız `Docs/` veya `.mdc` yazma.
3. **Docs önce:** Onay → `(A) Docs/` → `(B) .mdc`. `.mdc` güncel `Docs/` referanslarına dayanır.
4. **Tek doğruluk kaynağı:** Spec `Docs/` içinde; `.mdc` kopyalamaz — `Docs/<dosya>.md` §bölüm + uygulama notu. Harita: [docs-map.md](docs-map.md).
5. **Araştırma önce:** Roadmap, `Docs/`, komşu faz `.mdc`, kod boşluğu.
6. **Uygulama-hazır iterasyonlar:** Her iterasyon [iteration-blueprint.md](iteration-blueprint.md) iskeletinin **tamamını** içerir; geliştirici agent Plan moduna ihtiyaç duymadan kod yazar.
7. **Context window:** 1 chat ≈ 1 PR; ≤12 dosya; iterasyon başına Docs okuma ≤5 dosya (belirli §). Aşılıyorsa böl — bkz. iteration-blueprint §Context window.
8. **MVP disiplini:** Kapsam dışı roadmap Wave; faza eklenmez.
9. **Feature branch:** Her faz `.mdc` → `## Feature branch (zorunlu)`; `48-git-phase-branch.mdc`; main'de faz kodu yok.

## Akış

```
[1 Araştırma] → [2 Soru] → [3 Taslak + docs planı + iterasyon grain] → [4 Onay]
    → [5 Docs/ güncelle] → [6 Özet] → [7 .mdc — blueprint iterasyonlar] → [8 Doğrulama]
```

---

## Adım 1 — Araştırma

| Kaynak | Ne için |
| ------ | ------- |
| `Docs/10_IMPLEMENTATION_ROADMAP.md` | Faz no, §N.M alt maddeler, bağımlılık |
| `.cursor/rules/*-phase-*.mdc` | Komşu faz tonu |
| `Docs/01`–`08`, `06_SCREEN_CATALOG` | Spec bölümleri (pointer için § numarası) |
| `rg` / `SemanticSearch` | Kod vs doc boşluğu |

Çıktı: bulgular + **ilk tek soru**.

---

## Adım 2 — Soru döngüsü

```markdown
**Anladıklarım:** …
**Öneri (varsa):** …
**Soru:** …?
```

Sıra: Goal → katman → bağımlılık → **iterasyon grain (chat başına iş)** → test/Done → risk → faz no.

Yeterlilik: Goal, katmanlar, iterasyon sayısı, **her iterasyonun tek cümlelik teslimi**, Done, Explicit Don'ts, etkilenecek `Docs/` dosyaları → Adım 3.

---

## Adım 3 — Taslak (onay öncesi)

`Docs/` ve `.mdc` **yazma**. Sun:

```markdown
## Önerilen faz taslağı

**Dosya:** `.cursor/rules/NN-phase-XX-<slug>.mdc`
**Description:** [Faz N] … — K iterasyon/chat (…).

### Goal
…

### İterasyon özeti (grain)
| # | Teslim (1 cümle) | ~Dosya | Docs § |
| --- | --- | --- | --- |
| 1 | … | 4–8 | `Docs/10` §N.1, `Docs/02` … |

### MVP dışı / Done / Planlanan Docs güncellemeleri
…

Bu taslağı onaylıyor musun? Onay → önce Docs/, sonra blueprint kalitesinde .mdc.
```

Iterasyon tablosunda **grain** zorunlu: agent'ın tek chat'te bitirebileceği teslim + yaklaşık dosya sayısı + hangi `Docs/` § okunacak.

---

## Adım 4 — `Docs/` güncellemesi

Onay sonrası yalnızca Docs; `.mdc` yok.

1. [docs-map.md](docs-map.md) — minimum set.
2. Taslak tablosunu checklist; her dosyayı `Read` + `Grep` ile doğru bölüm.
3. `Docs/10`: `### Faz N` + §N.1…N.K alt maddeleri (`.mdc` iterasyonlarıyla birebir hizalı).
4. Tutarlılık: enum/route/`S-*` üçlüsü (`02`/`03`/`06`); MVP `Docs/00` uyumu.

Özet + "`.mdc` yazımına devam?" onayı → Adım 5.

---

## Adım 5 — `.mdc` yazımı (blueprint iterasyonlar)

[reference.md](reference.md) üst iskelet + **[iteration-blueprint.md](iteration-blueprint.md)** her iterasyon için.

### Her iterasyon zorunlu bölümler

| Bölüm | Amaç |
| ----- | ---- |
| Hedef | Ölçülebilir teslim |
| Teslim çıktısı | Somut artefaktlar |
| Önkoşullar | Önceki Stop + migration/env |
| Docs okuma sırası | ≤5 dosya, § + neden |
| Uygulama planı | Plan-modu adımları; fiil+path+Docs § |
| Dosya kapsamı | Oluştur/Güncelle/Dokunma tablosu |
| Spec → kod eşlemesi | ≥3 satır (scaffold istisnası belgeli) |
| Kalite kapıları | Test + deny + ruff/mypy/pytest |
| Bu iterasyonda yok | Scope duvarı |
| Risk / dikkat | Edge case, sızıntı uyarısı |
| Stop | Çalıştırılabilir komutlar |

### Yazım adımları

1. `Glob .cursor/rules/*-phase-*.mdc` — çakışma yok.
2. `Docs/10` §N.M ↔ `### İterasyon M` birebir.
3. Her uygulama planı maddesi en az bir `Docs/…` § referansı.
4. **Yasak:** Belirsiz "API spec'e bak"; tam request body kopyası; 50+ satır ağaç; tek iterasyonda çok katman.
5. Faz üstü: Goal, Feature branch, çalışma modeli ("Plan moduna geçme — iterasyon yeterli"), Required Context, Done, Explicit Don'ts.

Çıktı: dosya yolu, iterasyon sayısı, `Faz N — İterasyon 1` etiketi.

---

## Adım 6 — Doğrulama

**Docs/**

- [ ] Taslak + docs-map uygulandı
- [ ] `Docs/10` §N.M ↔ `.mdc` iterasyon sayısı uyumlu

**.mdc**

- [ ] Her iterasyon: iteration-blueprint 9+ bölüm dolu
- [ ] Docs okuma sırası: path + §; ≤5 dosya/iterasyon
- [ ] Uygulama planı ≥3 somut adım; Spec→kod ≥3 satır (veya scaffold notu)
- [ ] Stop'ta çalıştırılabilir komut
- [ ] Plan modu tekrarı gerektirmiyor (kör nokta yok)
- [ ] Feature branch + 1 chat ≈ 1 PR

---

## Ek kaynaklar

- [iteration-blueprint.md](iteration-blueprint.md) — iterasyon şablonu + örnek + bölme kuralları
- [reference.md](reference.md) — faz iskeleti
- [docs-map.md](docs-map.md) — Docs güncelleme haritası
- `Docs/10_IMPLEMENTATION_ROADMAP.md` Bölüm 9 — yaşam döngüsü

## Anti-pattern'ler

- ❌ Kısa iterasyon (yalnızca Hedef + Minimum bağlam + Stop)
- ❌ Plan modunu iterasyona deleg etmek ("implementasyonda planla")
- ❌ Tüm `Docs/` okutma — yalnızca okuma sırasındaki §
- ❌ Spec tablosunu `.mdc`'ye kopyalama
- ❌ Onaysız yazım; `.mdc` önce Docs sonra tersi
- ❌ Uydurma `S-*` / § / endpoint
- ❌ `~/.cursor/skills-cursor/` altına dosya

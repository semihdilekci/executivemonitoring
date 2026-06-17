---
name: phase-controller
description: Audits completed roadmap phase implementation against Docs and phase .mdc (Done Definition, API, screens, security, tests). Read-only — produces NN-phase-XX-fix.mdc remediation plan in .cursor/rules/ without modifying code. Does not suggest or write Docs/fix-reports/ unless the user explicitly asks. Use after phase implementation, before Human Gate, or when user mentions phase audit, gap analysis, or phase-controller.
disable-model-invocation: true
---

# Phase Controller

> **Cursor:** `.cursor/skills/phase-controller/`. Claude Code eşdeğeri: `.claude/skills/phase-controller/`. İçerik değişince **her iki kopyayı** senkron tut.
>
> **Eş:** `phase-creator` (plan → kod). **Bu skill:** kod → gap analizi → fix planı (kod **değiştirilmez**).

Faz implementasyonu bittikten sonra **read-only compliance audit** çalıştırır.

## Varsayılan çıktı (tek dosya)

**Yalnızca:** `.cursor/rules/NN-phase-XX-<slug>-fix.mdc` — remediation planı + gömülü audit bulguları (tek kaynak).

Fix oturumları `-fix.mdc` ile yürütülür; bu skill fix sırasında **tekrar invoke edilmez** (regression audit için ayrı oturum).

## Docs/fix-reports/ — yasak teklif

- ❌ `Docs/fix-reports/Faz-XX-<slug>-fix-report.md` **teklif etme**, onay şablonuna **ekleme**, varsayılan olarak **yazma**
- ❌ "Yazılacak dosyalar" listesinde `Docs/fix-reports/` gösterme
- ✅ Audit özeti sohbette sunulur; kalıcı artefakt fix `.mdc` içindeki **Audit bulguları** tablosu/bölümü
- ✅ Kullanıcı **açıkça** "fix report Docs'a yaz" derse → o zaman `Docs/fix-reports/` oluşturulabilir (istisna)

## Zorunlu kurallar

1. **Read-only:** Uygulama kodu, test, Prisma, `Docs/`, orijinal faz `.mdc` **değiştirilmez**. CI komutları çalıştırılabilir; fail **düzeltilmez**, bulgu olarak yazılır.
2. **Kanıt zorunlu:** Her bulgu en az bir kanıt: `path:satır`, grep çıktısı özeti, veya `Docs/XX` §Y vs kod karşılaştırması.
3. **Tek soru kuralı:** Keşif turunda tur başına **bir** soru (faz no, branch, kapsam daraltma).
4. **Onay kapısı:** Fix `.mdc` **taslağı** (sohbet özeti + bulgu listesi) kullanıcıya sunulur; onay olmadan dosya yazılmaz.
5. **Severity disiplini:** BLOCKER → HIGH → MEDIUM → LOW → INFO. BLOCKER = Human Gate fail / güvenlik ihlali / kritik Done maddesi eksik.
6. **Bulgu tipi:** `MISSING` | `WRONG` | `EXTRA` | `DOC_DRIFT` | `TEST_GAP` | `SECURITY` | `PATTERN`.
7. **Spec kaynağı:** `Docs/` + kaynak faz `.mdc` (Done Definition, Explicit Don'ts, Scope). Çelişki → Docs kazanır; bulgu `DOC_DRIFT` veya `WRONG` olarak etiketlenir.
8. **Fix scope sınırı:** Fix `.mdc` yalnızca audit bulgularını kapatır; yeni feature / sonraki faz scope'u **yasak**.

## Akış özeti

```
[1 Araştırma] → [2 Tek soru] → [3 Read-only audit] → [4 Bulgu sınıflandırma]
    → [5 Taslak (sohbet özeti + fix.mdc planı)] → [6 Onay] → [7 fix.mdc yazımı] → [8 Özet]
```

Detay matris: [verification-matrix.md](verification-matrix.md). Şablonlar: [reference.md](reference.md).

---

## Adım 1 — Araştırma

| Kaynak                                 | Ne için                                               |
| -------------------------------------- | ----------------------------------------------------- |
| `.cursor/rules/NN-phase-XX-<slug>.mdc` | Done Definition, iterasyonlar, Scope, Explicit Don'ts |
| `Docs/10_IMPLEMENTATION_ROADMAP.md`    | §Faz N deliverable, Human Gate, bağımlılık            |
| `Docs/03`, `06`, `02`, `07`, `08`      | Contract, ekran, şema, güvenlik, test                 |
| `Docs/11_UAT.md`                       | §Faz N (varsa) — UAT maddeleri audit notu             |
| `git log` / `git diff main...HEAD`     | Faz branch kapsamı (opsiyonel)                        |
| `rg`, `Glob`, `SemanticSearch`         | Kod varlığı, pattern taraması                         |

**Faz eşleme:** `59-phase-09-admin.mdc` → fix `59-phase-09-admin-fix.mdc` (aynı `NN`).

Çıktı: kısa bulgu hipotezleri + **tek soru** (faz no doğrulama veya branch adı).

---

## Adım 2 — Tek soru

Örnek:

```markdown
**Anladıklarım:** Faz 9 admin branch'inde audit isteniyor; kaynak `@59-phase-09-admin`.
**Soru:** Audit kapsamı tam faz mı, yoksa belirli iterasyon(lar) mı (örn. yalnızca İterasyon 7–10)?
```

Tam faz = Done Definition + tüm iterasyon hedefleri + Explicit Don'ts + scope creep.

---

## Adım 3 — Read-only audit

[verification-matrix.md](verification-matrix.md) boyutlarını sırayla uygula. Her boyut için:

1. Beklenen durumu spec'ten çıkar (checkbox / madde listesi)
2. Kodda kanıt ara
3. Sonuç: ✅ uyumlu | ⚠ bulgu | ➖ N/A (Explicit Don'ts veya "Bu iterasyonda yok")

**Read-only komutlar** (fail = bulgu, fix yok):

```bash
pnpm lint
pnpm typecheck
# Faz Done Definition'daki filtreye göre, örn.:
pnpm --filter @ethics/api test
pnpm test   # tam suite yalnızca audit notunda belirtilirse
```

Coverage script varsa çalıştır; eşik altı → `TEST_GAP`.

**Yasak:** `StrReplace`, `Write` (kod/spec docs), migration, commit, PR — **istisna:** onay sonrası yalnızca `.cursor/rules/NN-phase-XX-*-fix.mdc`.

---

## Adım 4 — Bulgu sınıflandırma

Her bulguya benzersiz ID: `F-<XX>-<NNN>` (ör. `F-09-001`).

| Severity    | Ne zaman                                                                                                 |
| ----------- | -------------------------------------------------------------------------------------------------------- |
| **BLOCKER** | Güvenlik baseline ihlali; kritik API/ekran yok; Explicit Don'ts ihlali; CI kırmızı (lint/typecheck/test) |
| **HIGH**    | Done Definition maddesi eksik/hatalı; negatif deny test yok; maker-checker backend enforced değil        |
| **MEDIUM**  | Pattern sapması (`@RequirePolicy` eksik tek endpoint); kısmi implementasyon                              |
| **LOW**     | İsimlendirme, doc güncellenmemiş, düşük risk test eksikliği                                              |
| **INFO**    | Gözlem, bilinçli erteleme kanıtı ("Bu iterasyonda yok" uyumlu)                                           |

**Genel durum:**

| Durum            | Koşul                           |
| ---------------- | ------------------------------- |
| `PASS`           | BLOCKER=0, HIGH=0               |
| `PASS_WITH_GAPS` | BLOCKER=0, HIGH>0 veya MEDIUM≥3 |
| `FAIL`           | BLOCKER≥1                       |

---

## Adım 5 — Taslak (onay öncesi)

Dosya **yazma**. Kullanıcıya özet (sohbet — kalıcı rapor değil):

```markdown
## Phase Controller — Faz N Audit Özeti

**Genel durum:** PASS | PASS_WITH_GAPS | FAIL
**Kaynak:** `.cursor/rules/NN-phase-XX-<slug>.mdc`
**Branch:** …

| Severity | Adet |
| -------- | ---- |
| BLOCKER  | …    |
| HIGH     | …    |

**Fix iterasyon özeti:** (fix.mdc'de kaç iterasyon, gruplama mantığı)

**Onay sonrası yazılacak dosya:**

- `.cursor/rules/NN-phase-XX-<slug>-fix.mdc` (bulgular bu dosyaya gömülür)

Bu taslağı onaylıyor musun?
```

`Docs/fix-reports/` path'ini bu şablonda **gösterme**.

---

## Adım 6 — Onay sonrası dosya yazımı

1. Fix `.mdc` — [reference.md § Fix Phase .mdc](reference.md); **Audit bulguları** bölümü tüm F-XX-NNN kayıtlarını içerir
2. `Docs/fix-reports/` **oluşturma** — kullanıcı açıkça istemedikçe

**Fix iterasyon gruplama:** BLOCKER+SECURITY önce → HIGH → MEDIUM/LOW. Domain sırası: schema/BE → FE → test. Her bulgu ID fix `.mdc`'de bir iterasyona map edilir.

---

## Adım 7 — Kullanıcıya kapanış özeti

```markdown
## Phase Controller tamamlandı

| Çıktı     | Path                                       |
| --------- | ------------------------------------------ |
| Fix planı | `.cursor/rules/NN-phase-XX-<slug>-fix.mdc` |

**Genel durum:** …
**Sonraki adım:** Fix için `@NN-phase-XX-<slug>-fix` + 「Faz N — Fix İterasyon 1」. Human Gate öncesi BLOCKER=0 hedeflenir.
```

---

## Ekosistem ilişkileri

| Bileşen                     | İlişki                                                                             |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `phase-creator`             | Faz **öncesi** plan; controller **sonrası** doğrulama                              |
| `Docs/11_UAT.md`            | Controller otomatik UAT işaretlemez; fix `.mdc` UAT maddelerine referans verebilir |
| `48-git-phase-branch`       | Fix oturumları aynı faz branch veya `fix/F<N>-*` branch — fix `.mdc`'de belirtilir |
| Human Gate (`Docs/10` §1.4) | Controller Human Gate'i **tamamlamaz**; girdi sağlar                               |

**Regression:** Fix iterasyonları bittikten sonra `@phase-controller` tekrar çalıştırılabilir; fix `.mdc` güncellenir veya `_v2` suffix — kullanıcı tercihi, önce sor.

---

## Anti-pattern'ler

- ❌ `Docs/fix-reports/` dosyasını teklif etmek veya varsayılan çıktı olarak listelemek
- ❌ Audit sırasında kod veya test düzeltmek
- ❌ Kanıtsız bulgu ("galiba eksik")
- ❌ Fix `.mdc`'de yeni feature / sonraki faz scope'u
- ❌ Orijinal faz `.mdc` veya `Docs/` spec dosyalarını audit sırasında değiştirmek
- ❌ Roadmap'te fazı "tamamlandı" işaretlemek
- ❌ Tek mesajda çoklu soru
- ❌ Onaysız fix `.mdc` yazmak
- ❌ `~/.cursor/skills-cursor/` altına dosya

## Ek kaynaklar

- [reference.md](reference.md) — fix `.mdc` iskeleti (+ isteğe bağlı Docs rapor şablonu)
- [verification-matrix.md](verification-matrix.md) — boyut × kanıt matrisi
- `.cursor/skills/phase-creator/reference.md` — kaynak faz `.mdc` yapısı
- `.cursor/skills/phase-creator/docs-map.md` — hangi doc ne zaman

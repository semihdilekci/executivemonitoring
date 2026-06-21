# CLAUDE.md / AGENTS.md Router Şablonu

`rules-architect` Adım G çıktısı. Proje adını ve tabloları docs keşfinden doldur. **Kural metni tekrarlanmaz.**

---

```markdown
# CLAUDE.md — <Proje Adı>

> Bu proje **`.cursor/rules/*.mdc`** altında tanımlı kural seti ile yönetilir.
> Bu dosya always-apply + glob + göreve-bağlı kuralların **yönlendiricisidir**.
> **Spec tek doğruluk kaynağı:** `docs/`. `.mdc` ile docs çelişirse docs kazanır.

---

## ⚙️ Çalışma Protokolü — Her Görevde

1. **Her zaman geçerli (00–04)** — özet aşağıda; tereddütte tam `.mdc` oku.
2. **Dosyaya dokunmadan önce** glob tablosundan ilgili kuralı oku.
3. **Görev prosedürüyse** (endpoint, ekran, migration…) how-to tablosundan ilgili `4x` kuralı oku.
4. **Faz çalışmasıysa** (`Faz N — İterasyon M`) ilgili `5x/6x-phase-*.mdc` oku.
5. Spec detayı için `docs/` path'ine git — rule'da kopyalanmış tablo arama.

> **Verimlilik:** Tüm `.mdc` dosyalarını okuma. Yalnızca dokunduğun dosya + görev tipine uygun kurallar.

---

## 📌 Her Zaman Geçerli (00–04 özet)

Tam metin: `.cursor/rules/0*.mdc`, `04-*.mdc`.

- **[00] Kimlik** — <1–2 cümle: ne, kim, stack pin>
- **[01] Felsefe** — MVP scope, test-first, self-review
- **[02] Naming** — TR UI / EN code, commit, error code
- **[03] Güvenlik** — 6 zorunlu kontrol; skip yasak
- **[04] Kalite** — coverage, CI, bundle, a11y eşikleri

---

## 🗂 Glob Yönlendirme

| Dosya deseni | Oku |
| --- | --- |
| `<backend genel glob>` | `10-...` |
| `<auth glob>` | `11-...` |
| … | … |
| `<frontend genel glob>` | `20-...` |
| `<test glob>` | `35-...` |

> Birden fazla desen eşleşebilir — hepsini uygula.

---

## 🛠 How-To Yönlendirme

| Görev türü | Oku |
| --- | --- |
| Yeni REST endpoint | `40-add-new-endpoint` |
| Yeni ekran | `41-add-new-screen` |
| Prisma migration | `42-add-prisma-migration` |
| Faz implementasyonu | `48-git-phase-branch` (+ ilgili `@NN-phase-XX-slug`) |
| … | … |

---

## 🚦 Faz Yönlendirme

Mesajda **「Faz N — İterasyon M」** belirt; `@NN-phase-XX-slug` invoke et. **Kod öncesi** faz feature branch aç (`48-git-phase-branch`).

| Faz | Kural |
| --- | --- |
| 0 … | `50-phase-00-...` |
| 1 … | `51-phase-01-...` |
| … | … |

Faz `.mdc` üretimi: `phase-creator` skill.

---

## 📚 docs/ — Nihai Kaynak

`<proje docs listesi — 00–10, adr/, processes/, design-system/ …>`

> Yeni faz / spec değişikliği → önce docs güncelle, sonra ilgili `.mdc` referansını doğrula.

---

## 🔁 Yer Konumu

Kural paketi: **`.cursor/rules/`**. Numara → dosya adı öneki (`14` → `14-backend-controllers.mdc`).
```

---

## Doldurma notları

- Glob tablosu: repo `Glob`/`rg` ile doğrulanmış path'ler; uydurma yok.
- Faz tablosu: yalnızca **yazılmış** phase `.mdc` satırları; eksik fazlar "phase-creator ile üretilecek" notu SKILL çıktısında kalır.
- Özet maddeler: ilgili `00–04` `.mdc`'den 5–8 bullet distile; tam metin kopyalama.

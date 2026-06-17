# Docs Güncelleme Haritası — Phase Creator

Faz onayından sonra `docs/` güncellemelerinde **tek doğruluk kaynağı** bu haritadır. `docs/10_IMPLEMENTATION_ROADMAP.md` Bölüm 9 (Doküman Yaşam Döngüsü) ile uyumlu.

**Altın kural:** Kod/spec çelişkisi → önce `docs/` güncelle, sonra `.mdc` yaz. `.mdc` içinde spec tekrarı yok — bölüm referansı.

---

## Çekirdek dokümanlar (numaralı)

| Dosya                                | Ne zaman güncelle                             | Tipik içerik                                    |
| ------------------------------------ | --------------------------------------------- | ----------------------------------------------- |
| `docs/00_PROJECT_OVERVIEW.md`        | MVP kapsamı / non-goal değişimi (nadir)       | In-scope / out-of-scope madde                   |
| `docs/01_DOMAIN_MODEL.md`            | Yeni entity, state machine, domain terim      | Entity diyagramı, geçiş tablosu                 |
| `docs/02_DATABASE_SCHEMA.md`         | Tablo/kolon/index/enum/migration              | Prisma karşılığı, constraint                    |
| `docs/03_API_CONTRACTS.md`           | Yeni/değişen endpoint                         | Request/response, error code                    |
| `docs/04_BACKEND_SPEC.md`            | Yeni servis pattern, middleware, modül yapısı | Nest modül konvansiyonu                         |
| `docs/05_FRONTEND_SPEC.md`           | Route ağacı, global FE pattern, lib           | `app/` route, state stratejisi                  |
| `docs/06_SCREEN_CATALOG.md`          | Yeni ekran veya kritik UX değişikliği         | `S-*` ID, permission, state'ler                 |
| `docs/07_SECURITY_IMPLEMENTATION.md` | Auth, encryption, rate limit, yeni control    | Bölüm + threat model notu                       |
| `docs/08_TESTING_STRATEGY.md`        | Yeni test türü, coverage hedefi, E2E journey  | Journey adı, risk seviyesi                      |
| `docs/09_DEV_WORKFLOW.md`            | CI/CD, release, branch, agent kuralları       | Süreç değişikliği                               |
| `docs/10_IMPLEMENTATION_ROADMAP.md`  | **Her yeni/güncellenen faz**                  | Faz başlığı, bağımlılık, iterasyon özeti, durum |

---

## Faz tipine göre minimum doküman seti

Aşağıdaki satırlar **minimum**; faz kapsamına göre ek satırlar ekle. Güncellenmeyen dosyaları taslakta **"Dokunulmaz"** olarak listele.

| Faz tipi                     | Zorunlu docs                                       | Sık eklenen                       |
| ---------------------------- | -------------------------------------------------- | --------------------------------- |
| **DB / schema**              | 02, 01 (entity), 10                                | 03 (DTO alanları)                 |
| **Backend API**              | 03, 02, 04, 07, 10                                 | 01, 08 (integration test)         |
| **Frontend ekran**           | 06, 05, 03 (read contract), 10                     | 07 (XSS/CSP notu)                 |
| **Full-stack feature**       | 01, 02, 03, 05, 06, 10                             | 04, 07, 08                        |
| **Yetki / RBAC**             | 01, 03, 04, 06, 07, 10                             | 02 (yoksa permission tablosu yok) |
| **UI / design system**       | 05, 06 (etkilenen), 10                             | `docs/lean-design-system/*`, ADR  |
| **Infra / IaC**              | 10, 09                                             | ADR `docs/adr/`                   |
| **Worker / cron**            | 03, 04, 10                                         | 02, 08                            |
| **Süreç tipi (KTİ benzeri)** | `docs/processes/<slug>.md`, 01, 02, 03, 05, 06, 10 | ADR                               |
| **Güvenlik sertleştirme**    | 07, 08, 10                                         | 03, 09                            |
| **Performans**               | 08, 10, 04                                         | 02 (index)                        |

---

## Yardımcı / özel dosyalar

| Dosya                                       | Ne zaman                                                                   |
| ------------------------------------------- | -------------------------------------------------------------------------- |
| `docs/adr/00NN-<slug>.md`                   | Mimari karar, stack sapması, güvenlik modeli değişimi (`45-write-adr.mdc`) |
| `docs/mimari-kararlar.md`                   | Holding düzeyi karar özeti (ADR ile çapraz)                                |
| `docs/processes/<slug>.md`                  | Yeni iş süreci tipi                                                        |
| `docs/templates/PROCESS_DESIGN_TEMPLATE.md` | Şablon değişmez; süreç için kopya → `processes/`                           |
| `docs/GAP_analysis.md`                      | Bilinçli spec–kod boşluğu kapatılıyorsa                                    |
| `docs/lean-design-system/*`                 | UI token/bileşen değişimi                                                  |

ADR numarası: mevcut `docs/adr/*.md` listesinden sonraki sıra.

---

## Güncelleme disiplini

1. **Önce oku:** İlgili dosyada mevcut bölümü `Grep` ile bul; aynı yapıda ekle (kopyala-yapıştır kalıbı).
2. **Screen Catalog:** `S-<DOMAIN>-<ACTION>` ID'si mevcut dosyada var mı kontrol et; yoksa tam bölüm ekle (route, permission, form, state'ler, TR mesajlar).
3. **API Contracts:** Endpoint başına request/response envelope + error code listesi.
4. **Roadmap:** `## 3. Faz Detayları` altında yeni `### Faz N — …` veya mevcut fazı genişlet; bağımlılık grafiği notu gerekirse Bölüm 2'ye tek satır.
5. **Tutarlılık:** Aynı terim tüm dosyalarda aynı (enum, permission, ekran ID, route path).
6. **Özet çıktı:** Güncelleme bitince kullanıcıya tablo: dosya → değişen bölüm (1 satır).

---

## .mdc'ye taşınmayan içerik

Bunlar **yalnızca** `docs/` içinde kalır; `.mdc` sadece referans verir:

- Tam API request/response örnekleri → `03_API_CONTRACTS`
- Ekran alan listesi ve UX state → `06_SCREEN_CATALOG`
- Tablo/kolon tanımı → `02_DATABASE_SCHEMA`
- Entity lifecycle → `01_DOMAIN_MODEL`
- Uzun dosya ağaçları (50+ satır) → ilgili spec veya roadmap; `.mdc`'de en fazla 10–15 satır özet ağaç

`.mdc`'de kalması gerekenler: Goal, iterasyon Hedef/Stop, **Minimum bağlam** (path + bölüm), **Bu iterasyonda yok**, Done Definition checklist, Explicit Don'ts.

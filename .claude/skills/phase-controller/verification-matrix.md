# Verification Matrix — Phase Controller

Her faz audit'inde uygulanacak boyutlar. Faz tipine göre **minimum set** zorunlu; diğerleri N/A ise raporda gerekçe.

Kaynak faz tipi → minimum docs: `.cursor/skills/phase-creator/docs-map.md`.

---

## Boyut özeti

| ID | Boyut | Birincil spec | Kod kanıt yöntemi |
| -- | ----- | ------------- | ----------------- |
| D1 | Done Definition | phase `.mdc` §Done Definition | Checklist ↔ dosya/test varlığı |
| D2 | İterasyon hedefleri | phase `.mdc` §İterasyon | Modül/route/API listesi |
| D3 | API contract | `Docs/03` | Controller, DTO, route prefix |
| D4 | Ekran kataloğu | `Docs/06` S-* | routes, pages, PermissionGate |
| D5 | DB şema | `Docs/02` | `schema.prisma`, migrations |
| D6 | Güvenlik baseline | `03`, `Docs/07` | Decorator, guard, masking grep |
| D7 | Explicit Don'ts | phase `.mdc` | Anti-pattern taraması |
| D8 | Scope creep | phase `.mdc` §Files NOT touched | Yeni dosya vs izinli scope |
| D9 | Test & coverage | `Docs/08`, Done Definition | test dosyaları, CI script |
| D10 | Pattern tutarlılığı | `04`, glob 10–16 | Error code, Zod, audit outbox |
| D11 | Roadmap deliverable | `Docs/10` §Faz N | Deliverable listesi |
| D12 | UAT hazırlık | `Docs/11` §Faz N | Not — otomatik PASS yok |

---

## D1 — Done Definition

**Yöntem:**

1. phase `.mdc` Done Definition maddelerini tabloya çıkar
2. Her madde için: ✅ kanıt | ❌ bulgu | ➖ N/A
3. ❌ → `MISSING` veya `WRONG`; severity Done maddesinin kritikliğine göre

**Kritik modül eşiği** (`04-quality-gates`): authz, workflow, document, audit, crypto, notification → eksik test/coverage = min HIGH.

---

## D2 — İterasyon hedefleri

**Yöntem:**

1. Her `### İterasyon N` **Hedef** satırını oku
2. **Yapılacaklar** maddelerini grep/Glob ile doğrula
3. **Bu iterasyonda yok** maddelerinin implemente edilmediğini doğrula (scope creep tersi)

İterasyon kısmi tamamlanmışsa: `HIGH` (Hedef cümlesi karşılanmıyor).

---

## D3 — API contract

**Yöntem:**

1. `Docs/03` ilgili bölümdeki endpoint listesi (roadmap / phase Required Context'ten)
2. `@Controller`, `@Get`, `@Post`, route path grep
3. `@RequirePolicy` — mutating + read internal
4. `@AuditAction` — mutating
5. Zod DTO — `packages/dto` import
6. Error code — `packages/shared/constants/error-codes.ts` domain pattern

| Sapma | Tip | Severity |
| ----- | --- | -------- |
| Endpoint yok | MISSING | BLOCKER (core) / HIGH |
| Policy eksik | SECURITY | BLOCKER |
| Audit eksik (mutating) | SECURITY | HIGH |
| Yanlış path/method | WRONG | HIGH |

---

## D4 — Ekran kataloğu

**Yöntem:**

1. `Docs/06` S-* ID listesi (phase Required Context)
2. `apps/web/src/routes/` + `features/**/pages/`
3. PermissionGate / RoleGuard — UX only notu; backend deny ayrı D6
4. TR UI label spot-check (opsiyonel LOW)

Eksik route/page → `MISSING` HIGH. Spec dışı ekran → `EXTRA` MEDIUM.

---

## D5 — DB şema

**Yöntem:**

1. `Docs/02` tablo/kolon
2. `apps/api/prisma/schema.prisma`
3. Migration varlığı (`prisma/migrations/`)
4. Encrypted alanlar — CryptoService, doğrudan `crypto` import yok (D6 overlap)

Eksik tablo/kolon → BLOCKER (data model). Index eksik → MEDIUM (Faz 11 defer edilebilir — raporda not).

---

## D6 — Güvenlik baseline

`03-security-baseline.mdc` 6'lı checklist — faz kapsamına giren maddeler:

| # | Kontrol | Kanıt |
| --- | ------- | ----- |
| 1 | Auth/session | auth modülü, cookie flags test |
| 2 | Authz 3-katman | PolicyGuard, PolicyScope, FieldMasking |
| 3 | Encryption | CryptoService usage |
| 4 | Input/dosya | Zod whitelist, upload pipeline |
| 5 | Audit | outbox same tx |
| 6 | KVKK/non-prod | seed sentetik, template no PII |

İhlal → `SECURITY` BLOCKER veya HIGH.

**Admin faz:** maker ≠ checker backend 403 test zorunlu HIGH.

---

## D7 — Explicit Don'ts

phase `.mdc` §Explicit Don'ts — her madde:

- İhlal kanıtı varsa → BLOCKER veya HIGH (metnin ciddiyetine göre)
- Uyumlu → tabloda ✅

Örnek (Faz 9): "Maker-checker UI-only" → backend same-user test yok = BLOCKER.

---

## D8 — Scope creep

**Yöntem:**

1. phase `.mdc` §Scope + §Files NOT touched
2. `git diff main...HEAD --name-only` (branch belirtildiyse)
3. Sonraki faz dosya/ekran/feature listesi ile çakışma

`EXTRA` — MEDIUM (bilinçli prep ise INFO + defer notu).

---

## D9 — Test & coverage

**Yöntem:**

1. Done Definition test maddeleri
2. `08_TESTING_STRATEGY` — negatif deny en az 1 (auth/workflow/document)
3. CI komut çıktısı (read-only)
4. Coverage script varsa eşik

| Durum | Tip | Severity |
| ----- | --- | -------- |
| Test dosyası yok | TEST_GAP | HIGH (kritik modül) |
| Deny senaryosu yok | TEST_GAP | HIGH |
| CI fail | TEST_GAP | BLOCKER |
| Coverage <% eşik | TEST_GAP | HIGH |

---

## D10 — Pattern tutarlılığı

Spot-check (tüm repo değil — faz scope dosyaları):

- `DomainException` + error code (magic string yok)
- Prisma `$transaction` + audit outbox (mutating domain)
- FE: `localStorage` yok, `dangerouslySetInnerHTML` yok
- Worker job pattern (faz worker kapsıyorsa)

Sapma → `PATTERN` MEDIUM.

---

## D11 — Roadmap deliverable

`Docs/10` §Faz N:

- Deliverable listesi vs D1/D3/D4 birleşik sonuç
- Human Gate maddeleri — controller **işaretlemez**, "hazır/değil" notu
- Vibe Coding Risk tablosu — bilinen riskler için ekstra grep

---

## D12 — UAT hazırlık

`Docs/11_UAT.md` §Faz N maddeleri:

- Bulgu ile cross-ref (F-XX → UAT ID)
- Controller UAT dosyasını **güncellemez**
- Faz 9 öncesi UAT maddeleri ➖ N/A notu

---

## Faz tipine göre minimum boyut seti

| Faz tipi | Zorunlu boyutlar |
| -------- | ---------------- |
| Scaffold / infra | D1, D8, D9, D11 |
| Backend API | D1–D3, D6–D9, D11 |
| Frontend ekran | D1, D2, D4, D8, D9, D11 |
| Full-stack | D1–D11 (D12 opsiyonel F9+) |
| Admin | D1–D11 + maker-checker D6/D7 |
| Security hardening | D6, D7, D9, D11, D12 |
| Performance | D9, D11 (+ D5 index defer notu) |

---

## Kanıt kalite seviyesi

| Seviye | Açıklama | Kabul |
| ------ | -------- | ----- |
| A | path:satır + spec § referans | ✅ Tercih |
| B | grep sayısı + dosya listesi | ✅ |
| C | "modül mevcut" genel ifade | ❌ Yetersiz |

Bulgu C seviyesindeyse rapora **yazma** — daha fazla araştır.

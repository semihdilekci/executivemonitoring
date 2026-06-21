---
name: add-process-type
description: Adds a new business process type (e.g. 5S Audit, TPM Round) to the Lean Management Platform end-to-end. Use when the user provides a filled Process Design Template (docs/templates/PROCESS_DESIGN_TEMPLATE.md) or asks to add/scaffold/implement a new lean process workflow alongside the existing KTİ (BEFORE_AFTER_KAIZEN) process. Drives three sequential phases — documentation updates, phase .mdc creation, and code implementation across DB, shared packages, backend (workflow + registry + controller + tasks dispatch), frontend (route + form + sidebar + filters), seeds, notifications and tests — strictly reusing existing ProcessTypeRegistry, permissions, notifications, audit and UI building blocks.
---

# Add New Process Type

Bu skill **yeni bir iş süreci tipini** (KTİ gibi) projeye baştan sona ekler: dokümantasyon → faz dosyası → kod. Doldurulmuş `docs/templates/PROCESS_DESIGN_TEMPLATE.md` üzerinden çalışır. **Hiçbir yeni klasör/abstraction yaratmaz** — KTİ baseline'ını (`ProcessTypeRegistry`, jenerik permission'lar, ortak notifications/email/audit) **birebir** kullanır.

## Quick Start

Kullanıcı doldurulmuş şablonu verdiğinde:

```
Task Progress:
- [ ] Phase 0: Validate template input
- [ ] Phase 1: Documentation updates (process .md + 02/03/05/06/10)
- [ ] Phase 2: Phase .mdc file generation (.cursor/rules/)
- [ ] Phase 3: Implementation (DB → shared → backend → tasks → frontend → seed → tests)
- [ ] Phase 4: Verification (lint, typecheck, tests)
```

Her phase **kullanıcı onayı** sonrası sıradakine geçer. Plan modunda başla, kullanıcı "geliştirmeye geç" deyince agent moduna döner.

---

## Required Inputs

Skill başlamadan önce kullanıcıdan al:

1. **Doldurulmuş şablon dosyası** — `docs/processes/<slug>.draft.md` veya path olarak verilen herhangi bir doldurulmuş `PROCESS_DESIGN_TEMPLATE.md` kopyası.
2. **Onay**: Kullanıcı "evet, başlat" diyene kadar **kod yazma**. Sadece dokümantasyon araştır.

Eğer şablon yoksa, kullanıcıya `docs/templates/PROCESS_DESIGN_TEMPLATE.md`'yi kopyalamasını ve doldurmasını söyle.

---

## Phase 0: Template Validation

**Hedef:** Şablonun §13 "Tamamlama Onayı" listesindeki tüm alanlar dolu mu?

### Adımlar

1. `Read` ile şablonu oku.
2. Aşağıdaki **kritik alanları** doğrula:

| Alan                 | Bulunduğu bölüm | Format kontrolü                                                   |
| -------------------- | --------------- | ----------------------------------------------------------------- |
| Sistem kodu (enum)   | §1              | `^[A-Z][A-Z0-9_]+$`, mevcut `ProcessType` değerleriyle çakışmaz   |
| displayId prefix     | §1              | 2-4 alphanumeric, mevcut prefix'lerle çakışmaz (`KTI` dolu)       |
| URL slug             | §1              | kebab-case                                                        |
| Yeni permission(lar) | §2.1            | `PROCESS_<TIP>_START` formatında                                  |
| Adımlar              | §3.2            | en az 1 step; her birinde order/step_key/assignee/SLA/actions     |
| Geçiş tablosu        | §3.3            | her allowed action → bir sonraki step veya terminal eşleştirilmiş |
| Start payload        | §4.1            | en az 1 field                                                     |
| Bildirimler          | §6.1            | en az 1 olay eşleştirmesi (genelde `task.assigned`)               |
| MVP dışı             | §11             | en az 1 madde                                                     |

3. Eksik varsa **dur**, kullanıcıya hangi alanların eksik olduğunu listele. Eksik tamamlanmadan ilerleme.

4. Mevcut çakışmaları tespit et:

```
Grep --pattern "<NEW_ENUM>" --path packages/shared-types
Grep --pattern "<PREFIX>-" --path apps
```

Çakışma varsa kullanıcıya başka bir kod/prefix öner.

5. **Onay isteği:** Şablonun özetini (TR ad, enum, prefix, adım sayısı, yeni permission'lar) kullanıcıya göster. "Devam edeyim mi?" sor (`AskQuestion` ile).

---

## Phase 1: Documentation Updates

**Hedef:** Şablonu finalize et + ilgili docs'ları güncelle. Henüz kod YAZMA.

### Adımlar

#### 1.1 Finalize the process design doc

- `docs/processes/<slug>.draft.md` → `docs/processes/<slug>.md` (rename via Write + Delete draft)
- Üst kısmına bölge ekle: "Status: Approved" + tarih
- Eğer skill `.draft.md` görmedi (kullanıcı direkt path verdi) → mevcut dosyayı yerinde kabul et

#### 1.2 Update `docs/02_DATABASE_SCHEMA.md`

`process_type` enum'un tanımlandığı bölümü bul (`Grep --pattern "process_type" --type md --path docs/02_DATABASE_SCHEMA.md`), yeni değeri ekle. Sequence ve displayId prefix tablosuna yeni satır ekle.

#### 1.3 Update `docs/03_API_CONTRACTS.md`

- `POST /api/v1/processes/kti/start` bölümünü model alarak yeni endpoint için aynı yapıda örnek ekle:
  - Request body JSON (şablonun §4.1)
  - Response 201 envelope
  - Error code'lar (`PERMISSION_DENIED`, `VALIDATION_FAILED`, `USER_NOT_FOUND`, `DOCUMENT_SCAN_PENDING` vb.)
- Process list endpoint'inin `processType` query filter dokümantasyonuna yeni enum'u ekle.

#### 1.4 Update `docs/05_FRONTEND_SPEC.md`

Route ağacına `processes/<slug>/start/page.tsx` ekle.

#### 1.5 Update `docs/06_SCREEN_CATALOG.md`

`S-KTI-START` bölümünü kopyala, **`S-<TIP>-START`** olarak yeni bölüm yaz:

- Route: `/processes/<slug>/start`
- Permission: `PROCESS_<TIP>_START`
- Form alanları (şablonun §4.1, §5.3)
- State'ler: loading/empty/error/permission-denied/success (§5.4)
- TR mesajlar (§5.5)

#### 1.6 Update `docs/10_IMPLEMENTATION_ROADMAP.md`

Roadmap son fazından sonra yeni faz başlığı ekle:

```
### Faz <XX>: <TR_AD> Süreci (post-MVP / Wave 1)
- displayId prefix: <PREFIX>
- ProcessTypeRegistry pattern kullanır — KTİ baseline tekrarı
- İterasyonlar: <iterasyon_sayisi>
- Bağımlılık: Faz 5, Faz 6, Faz 7 (notifications) tamamlanmış olmalı
```

#### 1.7 ADR (opsiyonel)

Şablon §12.1'de "ADR gerekli" işaretlendiyse: `docs/adr/0XYZ-<slug>.md` yaz. MADR 3.0 format (`.cursor/rules/45-write-adr.mdc`). Aksi takdirde atla.

### Phase 1 Done Criteria

- [ ] `docs/processes/<slug>.md` finalize edildi
- [ ] 02, 03, 05, 06, 10 docs güncellendi
- [ ] (Opsiyonel) ADR yazıldı
- [ ] Kullanıcı dokümantasyonu inceleyip "OK" dedi

**STOP.** Kullanıcı onayı al, sonra Phase 2'ye geç.

---

## Phase 2: Phase .mdc Generation

**Hedef:** Bu sürecin geliştirilmesi için bir Cursor Rule (`.mdc`) üret. Skill bu dosyayı ileride **agent context'ine attach etmek için** üretir — kendisi kodlama yaparken kullanmasına gerek yok.

### Adımlar

1. **NN numarası belirle:** `Glob` ile `.cursor/rules/*-phase-*.mdc` listele. En yüksek `NN` değerini bul, +1 ver. Aralık genelde 60-69.
2. **Phase template'i oku:** `.cursor/skills/add-process-type/phase-template.md`.
3. Tüm placeholder'ları doldur:
   - `<NN>` → bulunan numara
   - `<XX>` → faz numarası (genelde NN-50, örn. 62 → Faz 12)
   - `<TR_AD>` → şablonun §1 Türkçe ad
   - `<NEW_ENUM>` → şablonun §1 sistem kodu
   - `<PREFIX>` → displayId prefix
   - `<slug>` → kebab-case
   - `<Slug>` → PascalCase
   - `<TIP>` → permission key UPPER kısmı
   - `<iterasyon_sayisi>` → 4 (KTİ ile uyumlu), karmaşıksa 5
4. Doldurulmuş içeriği `.cursor/rules/<NN>-phase-<XX>-<slug>.mdc` olarak yaz.
5. **Önemli:** `phase-template.md`'in _sadece_ triple-backtick markdown bloğunun içindeki kısım yazılır — şablon açıklamaları DAHİL EDİLMEZ.

### Phase 2 Done Criteria

- [ ] `.cursor/rules/<NN>-phase-<XX>-<slug>.mdc` oluşturuldu
- [ ] Front-matter `description` net (NEW_ENUM ve PREFIX içermeli)
- [ ] Tüm placeholder'lar dolu (Grep ile `<[A-Z]` doğrula)
- [ ] Kullanıcı dosyayı inceledi

**STOP.** Kullanıcı onayı al, sonra Phase 3'e geç.

---

## Phase 3: Implementation

**Hedef:** Üretilen faz dosyasındaki iterasyonları sırayla uygula. Her iterasyon ayrı PR'a karşılık gelir; tek session'da hepsini bitirme.

Tüm dosya konumları ve kalıpları için `reference.md`'yi rehber al. Kritik kurallar:

### Genel Kurallar

- **Kod kopyalama, üretme:** KTİ baseline dosyalarını (`kti.workflow.ts`, `KtiStartForm.tsx`, vb.) **şablon** olarak oku, yeni dosyaları aynı pattern'le yaz.
- **Şablon yeniden okuma:** Her iterasyon başında `docs/processes/<slug>.md`'yi tekrar oku — context drift'i önler.
- **Tek doğruluk kaynağı:** Tasarım kararı çelişiyorsa şablon kazanır; şablon eksikse kullanıcıya sor, varsayım yapma.
- **Hardcode yasak:** `process_type === '<NEW_ENUM>'` if/else `ProcessesService`'te yer almaz — registry üzerinden.

### İterasyon Sırası (faz dosyasından)

#### İterasyon 1 — DB + Shared Packages + Workflow

1. **DB migration:**
   - `apps/api/prisma/schema.prisma` → `enum ProcessType` içine `<NEW_ENUM>` ekle.
   - Migration: `pnpm --filter api prisma migrate dev --name add_<slug>_process_type` — sonra dosyayı manuel düzenle:
     ```sql
     ALTER TYPE "ProcessType" ADD VALUE '<NEW_ENUM>';
     CREATE SEQUENCE "process_seq_<snake_case>" START 1;
     ```
   - `42-add-prisma-migration.mdc` kuralına uy (expand-only, no destructive ops).

2. **shared-types** (`packages/shared-types/src/permission.ts`):
   - `Permission` enum'a yeni key
   - `PERMISSION_METADATA` map'ine yeni entry
   - `permission.test.ts` count assertion'ları güncelle

3. **shared-schemas** (`packages/shared-schemas/src/processes.schemas.ts`):
   - `PROCESS_TYPE_FILTER` array'ine ekle
   - `<Slug>StartBodySchema` (KtiStartBodySchema'yı şablon olarak kopyala, alanları §4.1'den al). `.strict()` zorunlu.
   - `<Slug>StartInput` export et
   - `index.ts` re-export

4. **Workflow class** (`apps/api/src/processes/workflows/<slug>.workflow.ts`):
   - `kti.workflow.ts`'i şablon al
   - `STEPS` array'i şablonun §3.2'den
   - `resolveAssigneeUserIdForStep` mantığı §3.2 "Assignee Kaynak" sütunundan
   - `getListActiveStepLabel` §4.3'ten
   - Unit testleri: `<slug>.workflow.test.ts` (`kti.workflow.test.ts` şablonu)

5. **Registry register** (`processes.module.ts` + `process-type-registry.service.ts`):
   - Provider listesine `<Slug>Workflow` ekle
   - `onModuleInit`'te `this.register(...)`

6. **Seed** (`apps/api/prisma/seed.ts`):
   - `ALL_PERMISSION_KEYS` array'ine yeni permission key (string) ekle
   - Demo data (opsiyonel, dev environment için)

7. **Doğrulama:**
   - `pnpm --filter @leanmgmt/shared-types test`
   - `pnpm --filter @leanmgmt/shared-schemas test`
   - `pnpm --filter api test -- workflow`
   - `pnpm lint && pnpm typecheck`

**İterasyon 1 PR onayı** beklenmesi gerekiyor.

#### İterasyon 2 — Start Endpoint + Task Complete Dispatch

1. **Service start metodu** (`apps/api/src/processes/processes.service.ts`):
   - `startKti`'yi şablon al
   - Adımlar: user lookup → doküman kontrolü → workflow al → sequence → displayId → `prisma.$transaction` → initiation task COMPLETED + manager task PENDING → assignee insert → event emit
   - Tip-özel exception'ları kullan (`<Slug>CompanyMismatchException`, `<Slug>ManagerRequiredException`)

2. **Controller** (`processes.controller.ts`):
   - `startKti`'yi şablon al
   - `@Post('<slug>/start')` + `@RequirePermission(Permission.PROCESS_<TIP>_START)` + `@Throttle({ default: { limit: 10, ttl: 60_000 }})` + `@Audit('START_PROCESS', 'process')`

3. **Exceptions** (`processes.exceptions.ts`):
   - KTİ exception'larını şablon al
   - Tip-özel exception sınıfları (örn: `<Slug>CompanyMismatchException`)

4. **Tasks dispatch** (`apps/api/src/tasks/tasks.service.ts`):
   - **KRİTİK:** `process.processType !== 'BEFORE_AFTER_KAIZEN'` guard'ı genişlet.
   - Yol A (hızlı): `SUPPORTED_TYPES` array'ine `<NEW_ENUM>` ekle, `<Slug>` için `completeManager` / `completeRevision` benzeri handler'lar yaz.
   - Yol B (doğru): `base-workflow.interface.ts`'e `applyCompletion()` method'u ekle, refactor (`44-refactor-to-pattern.mdc`). **İlk yeni tipte Yol A, ikincide Yol B.**

5. **Step labels backend** (varsa, `kti-task-step.ts` benzeri): yeni step_key mapping.

6. **Integration test** (`apps/api/test/processes-<slug>.integration.test.ts`):
   - Happy: start → 201 → displayId regex `^<PREFIX>-\d{6}$` → task1 COMPLETED + task2 PENDING
   - Edge: manager yok → 422 USER_NOT_FOUND
   - Edge: doküman PENDING_SCAN → 409 DOCUMENT_SCAN_PENDING (varsa)
   - Edge: permission yok → 403
   - Edge: company mismatch (varsa) → 422

7. **Doğrulama:** `pnpm --filter api test:int -- <slug>`.

#### İterasyon 3 — Frontend

1. **Sayfa** (`apps/web/src/app/(app)/processes/<slug>/start/page.tsx`):
   - KTİ start page'i şablon al

2. **Form** (`apps/web/src/components/processes/<Slug>StartForm.tsx`):
   - `KtiStartForm.tsx` şablon al
   - Çok adımlı: bilgi → (varsa) doküman upload → gözden geçir + ONAYLIYORUM kutusu

3. **Mutation** (`apps/web/src/lib/queries/processes.ts`):
   - `useStartKti` şablon al → `useStart<Slug>`

4. **Sidebar** (`AppSidebarNav.tsx`): `<PermissionGate permission="PROCESS_<TIP>_START">` link

5. **Liste filtresi** (`ProcessList.tsx`, `ProcessAdminList.tsx`): tip dropdown'una `{ value: '<NEW_ENUM>', label: '<TR_AD>' }`

6. **Step labels frontend** (`apps/web/src/lib/step-labels.ts`): yeni step_key TR etiket

7. **Breadcrumb regex** (`apps/web/src/lib/app-breadcrumbs.ts` veya benzeri): `DISPLAY_ID_RE` genişlet

8. **Task aksiyonları** (`TaskActions.tsx`, `TaskDetail.tsx`): yeni step_key için action butonları (gerekiyorsa)

9. **Doğrulama:** `pnpm --filter web typecheck && pnpm --filter web lint && pnpm --filter web test`

#### İterasyon 4 — Bildirim + E-posta + E2E

1. **Domain events** (`notifications/notification-domain.events.ts`): yeni event tipi nadiren gerekir; jenerik `task.assigned`, `task.completed`, `process.cancelled` zaten reuse.

2. **E-posta şablonları:** Şablonun §6.2 tablosundaki key'leri seed'e veya admin panele ekle (`docs/03_API_CONTRACTS.md` 9.9 email templates endpoint).

3. **Playwright** (`apps/web/test/processes-<slug>-start.spec.ts`):
   - Login → menüden başlat → form submit → success toast → redirect detay

4. **Audit log:** Integration test'te audit_logs tablosunda `START_PROCESS` kaydının var olduğunu assert et.

5. **Doğrulama (faz tamamı):**
   ```
   pnpm lint
   pnpm typecheck
   pnpm test
   pnpm --filter web test:e2e -- <slug>
   ```

### Phase 3 Done Criteria

Faz dosyasındaki "Done Definition" tüm checkbox'lar tikli.

---

## Phase 4: Verification

Her iterasyon sonrası kullanıcıya çıktıyı göster:

- Hangi dosyalar değişti (`git status`)
- Test sonuçları
- Lokal smoke yapması için açık talimat

Final faz sonunda:

- `docs/10_IMPLEMENTATION_ROADMAP.md`'de yeni faz check işareti
- Roadmap'te human gate'i geçtiğinde belirt

---

## Critical Constraints (Sıkı Uy)

- **Türkçe dil kuralı:** User-facing string TR; identifier İngilizce. (`02-language-naming.mdc`)
- **Permission decorator zorunlu:** Her mutating endpoint'te `@RequirePermission(...)`.
- **Audit decorator zorunlu:** State değiştiren her endpoint'te `@Audit(...)`.
- **Zod schema strict:** `.strict()` her shared schema'da.
- **No new abstractions:** Mevcut `ProcessTypeRegistry`, `ProcessWorkflow`, `Notifications`, `Audit`, `Document scan` altyapısı **olduğu gibi** kullanılır.
- **MVP kapsamı:** Şablon §11 "Açık Yasaklar" listesindeki şeyleri ekleme.
- **Test yazılmadan commit yok:** `01-coding-philosophy.mdc` test-first kuralı.
- **Self-review:** Her iterasyon sonu `04-quality-gates.mdc` checklist'i.

---

## Common Pitfalls (Yapma!)

| Yanlış                                                             | Doğru                                                                                    |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Yeni klasör `apps/api/src/five-s/` yaratmak                        | `apps/api/src/processes/workflows/five-s-audit.workflow.ts` (mevcut klasörde dosya ekle) |
| Yeni Permission `FIVE_S_AUDIT_VIEW` eklemek                        | `PROCESS_VIEW_ALL` (jenerik) reuse                                                       |
| Yeni cancel endpoint `/processes/5s/cancel`                        | Jenerik `/processes/:displayId/cancel` zaten çalışıyor                                   |
| Yeni notification type `5s_audit.assigned`                         | Jenerik `task.assigned` event'i reuse                                                    |
| displayId UUID veya rastgele                                       | PostgreSQL sequence + `<PREFIX>-NNNNNN`                                                  |
| Hardcode `if (processType === 'FIVE_S_AUDIT')` ProcessesService'te | Registry üzerinden `processTypeRegistry.getWorkflow(type)`                               |
| `KtiStartForm`'u parametre ile dynamic yapmak                      | Yeni bileşen `<Slug>StartForm.tsx` paralel olarak yaz                                    |

---

## Resources

- **Şablon:** `docs/templates/PROCESS_DESIGN_TEMPLATE.md`
- **Proje haritası (KTİ baseline):** [reference.md](reference.md)
- **Phase .mdc şablonu:** [phase-template.md](phase-template.md)
- **İlgili rules:**
  - `13-backend-processes.mdc` — ProcessTypeRegistry
  - `40-add-new-endpoint.mdc` — endpoint ekleme
  - `41-add-new-screen.mdc` — sayfa ekleme
  - `42-add-prisma-migration.mdc` — migration
  - `43-add-new-permission.mdc` — permission ekleme
  - `44-refactor-to-pattern.mdc` — task dispatch refactor için

---

## Final Output (Skill bittiğinde kullanıcıya ver)

```
Süreç eklendi: <TR_AD> (`<NEW_ENUM>`, prefix `<PREFIX>`)
Faz: .cursor/rules/<NN>-phase-<XX>-<slug>.mdc
Tasarım: docs/processes/<slug>.md
Migration: <timestamp>_add_<slug>_process_type

Test sonuçları:
- shared-types: PASS
- shared-schemas: PASS
- api unit + integration: PASS
- web typecheck + lint: PASS
- e2e smoke: PASS

Sonraki adım: PR aç, human gate review.
```

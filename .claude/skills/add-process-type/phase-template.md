# Phase .mdc Template

Skill bu şablonu doldurarak `.cursor/rules/<NN>-phase-<XX>-<slug>.mdc` dosyası üretir. Tüm `<...>` placeholder'larını şablonun (`docs/processes/<slug>.md`) içeriğinden türet.

**NN seçimi:** `.cursor/rules/` altındaki en yüksek 5N-phase-\* numarasını bul, **+1** ver. (Faz 12'den sonra → 62, 63, ...)
**XX:** Süreç sıra numarası — örn. 13 (Faz 13: 5S Audit).
**slug:** kebab-case enum (`five-s-audit`).

---

```markdown
---
description: "[Faz <XX>] <TR_AD> süreci — <iterasyon_sayisi> iterasyon/chat (workflow+state machine → start API → frontend → bildirim+test). Mesajda 'Faz <XX> — İterasyon N' belirt."
---

# Faz <XX>: <TR_AD> Süreci (`<NEW_ENUM>`)

## Goal

ProcessTypeRegistry pattern'i ile yeni süreç tipi `<NEW_ENUM>` (displayId prefix `<PREFIX>`): <2-3 cümle süreç tanımı; aşamalar + assignee tip-özetleri>. Mevcut KTİ pattern'i ile birebir uyumlu — yeni klasör/abstraction eklenmez. **Task complete dispatch'i (`tasks.service.ts`)** registry-tabanlı olmadığı için yeni tip için genişletilir (bkz. İterasyon 2).

## Bu fazın çalışma modeli (iterasyonlar)

`@<NN>-phase-<XX>-<slug>` + **"Faz <XX> — İterasyon N"**.

### İterasyon 1 — DB + shared packages + workflow

**Hedef:**

- `apps/api/prisma/schema.prisma` → `enum ProcessType` + yeni değer
- Migration: `ALTER TYPE` + `CREATE SEQUENCE process_seq_<snake_case>`
- `packages/shared-types`: `Permission.PROCESS_<TIP>_START` + metadata
- `packages/shared-schemas`: `<Slug>StartBodySchema` + `PROCESS_TYPE_FILTER` genişlet
- `apps/api/src/processes/workflows/<slug>.workflow.ts` + unit testleri
- Registry register (`processes.module.ts` + `process-type-registry.service.ts`)
- Seed: `ALL_PERMISSION_KEYS` + demo data

**Minimum bağlam:**

- `docs/processes/<slug>.md` (tasarım kararı)
- `docs/02_DATABASE_SCHEMA.md` Bölüm 6.4 (processes)
- `.cursor/rules/13-backend-processes.mdc` (registry pattern)
- `.cursor/rules/43-add-new-permission.mdc`
- `.cursor/rules/42-add-prisma-migration.mdc`

**Bu iterasyonda yok:** start endpoint kodu, frontend, task complete dispatch.

**Stop:** [ ] Workflow unit testleri green; [ ] migration locally apply edildi (`prisma migrate dev`); [ ] `pnpm lint && pnpm typecheck` green. PR/onay.

### İterasyon 2 — Start endpoint + task complete dispatch + integration test

**Hedef:**

- `ProcessesService.start<Slug>()` (KTİ patternine bire bir uyum)
- `ProcessesController` → `@Post('<slug>/start')` + throttle 10/dk + `@Audit`
- `processes.exceptions.ts` → tip-özel exception sınıfları
- `TasksService.complete` → guard'ı genişlet veya registry-tabanlı dispatch (bkz. reference §6)
- `apps/api/test/processes-<slug>.integration.test.ts` (happy + edge case)

**Minimum bağlam:**

- `docs/03_API_CONTRACTS.md` Bölüm 9.5–9.6
- `.cursor/rules/14-backend-controllers.mdc`
- `.cursor/rules/40-add-new-endpoint.mdc`

**Bu iterasyonda yok:** frontend, bildirim.

**Stop:** [ ] Integration test green (happy + min 5 edge case); [ ] displayId format `^<PREFIX>-\d{6}$` regex assertion. PR/onay.

### İterasyon 3 — Frontend (start sayfası + form + sidebar + liste)

**Hedef:**

- `apps/web/src/app/(app)/processes/<slug>/start/page.tsx`
- `apps/web/src/components/processes/<Slug>StartForm.tsx` (KtiStartForm şablonu, çok adımlı)
- `apps/web/src/lib/queries/processes.ts` → `useStart<Slug>` mutation
- `AppSidebarNav.tsx` → `PermissionGate` ile menü
- `ProcessList` + `ProcessAdminList` → tip filtresine yeni seçenek
- `step-labels.ts` → yeni step_key TR etiketleri
- `app-breadcrumbs.ts` → `DISPLAY_ID_RE` genişlet
- `TaskActions` / `TaskDetail` → yeni step_key action butonları (gerekiyorsa)

**Minimum bağlam:**

- `docs/05_FRONTEND_SPEC.md`
- `docs/06_SCREEN_CATALOG.md` → `S-<TIP>-START`
- `.cursor/rules/20-frontend-architecture.mdc` + `21-frontend-routes.mdc` + `22-frontend-forms.mdc`

**Bu iterasyonda yok:** Playwright E2E full journey (İter 4).

**Stop:** [ ] Start sayfası elle test (form submit → success toast → detay redirect); [ ] `pnpm --filter web typecheck`, lint green. PR/onay.

### İterasyon 4 — Bildirim + e-posta şablonu + E2E smoke

**Hedef:**

- E-posta şablonları (admin panel veya seed) → şablonun §6.2 tablosundaki key'ler
- Domain event handler'ları (eğer yeni event tipi eklendiyse — genelde reuse)
- `apps/web/test/processes-<slug>-start.spec.ts` Playwright happy path
- Audit log entries integration assertion

**Stop:** Faz <XX> Done Definition aşağıdaki checkbox'lar; roadmap işareti.

## Required Context

- `docs/processes/<slug>.md` — tek doğruluk kaynağı; tüm tasarım kararları burada
- `docs/01_DOMAIN_MODEL.md` Bölüm 3-4
- `docs/02_DATABASE_SCHEMA.md` Bölüm 6.4, 9-11
- `docs/03_API_CONTRACTS.md` Bölüm 9.5, 9.6
- `docs/06_SCREEN_CATALOG.md` — `S-<TIP>-START`

## Scope (repo ile hizalı)

### Backend
```

apps/api/src/processes/workflows/<slug>.workflow.ts # YENİ
apps/api/src/processes/workflows/<slug>.workflow.test.ts # YENİ
apps/api/src/processes/processes.service.ts # genişlet: start<Slug>()
apps/api/src/processes/processes.controller.ts # genişlet: @Post('<slug>/start')
apps/api/src/processes/processes.module.ts # genişlet: provider + register
apps/api/src/processes/process-type-registry.service.ts # genişlet: register
apps/api/src/processes/processes.exceptions.ts # genişlet: tip-özel exception
apps/api/src/tasks/tasks.service.ts # genişlet: dispatch
apps/api/prisma/schema.prisma # genişlet: ProcessType enum
apps/api/prisma/migrations/<timestamp>_add_<slug>/migration.sql # YENİ
apps/api/prisma/seed.ts # genişlet: permission + demo
apps/api/test/processes-<slug>.integration.test.ts # YENİ

```

### Frontend
```

apps/web/src/app/(app)/processes/<slug>/start/page.tsx # YENİ
apps/web/src/components/processes/<Slug>StartForm.tsx # YENİ
apps/web/src/lib/queries/processes.ts # genişlet
apps/web/src/lib/step-labels.ts # genişlet
apps/web/src/lib/app-breadcrumbs.ts # genişlet (regex)
apps/web/src/components/layout/AppSidebarNav.tsx # genişlet
apps/web/src/components/processes/ProcessList.tsx # genişlet (filtre)
apps/web/src/components/processes/ProcessAdminList.tsx # genişlet (filtre)
apps/web/src/components/tasks/TaskActions.tsx # genişlet (gerekiyorsa)
apps/web/test/processes-<slug>-start.spec.ts # YENİ

```

### Shared
```

packages/shared-types/src/permission.ts # genişlet: enum + metadata
packages/shared-types/src/permission.test.ts # genişlet
packages/shared-schemas/src/processes.schemas.ts # genişlet: schema + filter
packages/shared-schemas/src/index.ts # genişlet: re-export

```

## Constraints

- **Registry zorunlu** — `ProcessesService`'te `process_type === '<NEW_ENUM>'` hard-coded if/else yasak; her zaman `processTypeRegistry.getWorkflow(type)` üzerinden.
- **DisplayId format**: `<PREFIX>-NNNNNN` (sıfır pad 6 hane). PostgreSQL sequence + transaction içinde `nextval(...)`.
- **Tek doküman whitelist**: MIME tipleri `docs/03_API_CONTRACTS.md` ile sınırlı. Yeni tip eklenmez (PDF + image).
- **State machine strict**: geçersiz transition → typed exception (`InvalidWorkflowTransitionException` veya tip-özel).
- **Permission decorator**: `@RequirePermission(Permission.PROCESS_<TIP>_START)` zorunlu.
- **Audit**: `@Audit('START_PROCESS', 'process')` zorunlu.
- **Rate limit start**: 10/dk/user (KTİ ile aynı).
- **Manager yoksa 422** `USER_NOT_FOUND` (assignee `manager_user_id` kullanıyorsa).
- **Reuse**: cancel/rollback/list/detail jenerik endpoint'ler **değiştirilmez** — yeni tip otomatik desteklenir.

## Done Definition

- [ ] `enum ProcessType` ve seed migration apply edildi
- [ ] `<Slug>Workflow` registry'de register; unit testleri ≥85% line cov.
- [ ] `POST /api/v1/processes/<slug>/start` integration test (happy + 5 edge)
- [ ] `displayId` format `^<PREFIX>-\d{6}$` doğrulandı
- [ ] `TasksService.complete` yeni tip için çalışıyor (her allowed action için)
- [ ] Start permission seed'de superadmin + ilgili rollerde
- [ ] Start sayfası lokal smoke; form submit + redirect çalışıyor
- [ ] Sidebar menü `PermissionGate` ile çıkıyor
- [ ] Tip filtresi liste + admin liste dropdown'unda
- [ ] Breadcrumb regex yeni prefix'i tanıyor
- [ ] Bildirim akışı: `task.assigned`, `task.completed` her adımda doğru hedef kullanıcıya gidiyor
- [ ] E-posta şablonları seed/db'de
- [ ] Audit log her aksiyonda kayıt
- [ ] Playwright happy path green
- [ ] `pnpm lint && pnpm typecheck && pnpm test` green

## Explicit Don'ts

- Yeni klasör/abstraction yaratmak (registry zaten genişletilebilir)
- KTİ'deki dosyaları override etmek (paralel implementasyon)
- displayId'yi UUID veya global counter ile üretmek (sequence zorunlu)
- Cancel/rollback için tip-özel endpoint eklemek (jenerik var)
- Permission `PROCESS_*_VIEW` veya `*_COMPLETE` eklemek — view/complete generic permission'larla yapılır
- `dangerouslySetInnerHTML`, manuel HTML sanitization
- <Şablonun §11 "Açık Yasaklar" listesinden import>

## Related ADRs

- ADR-0016: ProcessTypeRegistry
- ADR-0017: State machine
- <Yeni süreç pattern'den sapıyorsa → yeni ADR link>

---

Faz <XX> human gate: `docs/10_IMPLEMENTATION_ROADMAP.md` — Faz <XX> bölümü.
```

---

## Skill için Kullanım Notları

1. Bu şablonu **string template** olarak kullan. `<NN>`, `<XX>`, `<TR_AD>`, `<NEW_ENUM>`, `<PREFIX>`, `<slug>`, `<Slug>`, `<TIP>` tüm yerlerini doldur:
   - `<TIP>` = enum kodun UPPER kısmı (örn. `FIVE_S` → `PROCESS_FIVE_S_START`)
   - `<Slug>` = PascalCase (örn. `FiveSAudit`)
   - `<slug>` = kebab-case (örn. `five-s-audit`)
   - `<PREFIX>` = displayId prefix (örn. `5SA`)

2. NN değeri için: `ls .cursor/rules/ | grep -E '^[0-9]+' | sort` ile en yüksek prefix'i bul, +1 ver.

3. İterasyon sayısı genelde **4** (KTİ ile uyumlu); süreç çok karmaşıksa +1.

4. Dosyayı oluşturduktan sonra `pnpm lint` çalıştırmak gerekmez — `.mdc` dosyalar lint'e dahil değil.

# Process Type Implementation Reference (KTİ Baseline Map)

Bu dosya, `add-process-type` skill'inin geliştirme aşamasında **hangi dosyaya ne ekleyeceğini** bulması için KTİ implementasyonunun haritasıdır. Yeni bir tip eklerken **aynı kalıpları** kopyala — yeni klasör/abstraction yaratma.

---

## 1. Dokümantasyon (Faz "Dokümantasyon")

| Doküman                             | Ne eklenir                                                                                                                                            |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/processes/<slug>.md`          | **YENİ** — şablondan üretilmiş, doldurulmuş süreç tasarım dosyası. Skill `.draft.md` → `.md` olarak finalize eder.                                    |
| `docs/02_DATABASE_SCHEMA.md`        | `process_type` enum'a yeni değer; yeni sequence (`process_seq_<slug>`); displayId prefix tablosu.                                                     |
| `docs/03_API_CONTRACTS.md`          | Yeni `POST /api/v1/processes/<slug>/start` endpoint örneği + request/response JSON + error code'lar. Liste filtresine `processType` enum genişlemesi. |
| `docs/05_FRONTEND_SPEC.md`          | Route ağacına `processes/<slug>/start/page.tsx` ekle. Query key listesine ekle.                                                                       |
| `docs/06_SCREEN_CATALOG.md`         | `S-<TIP>-START` için tam ekran tanımı (KTİ start ile aynı şablon). Mevcut S-PROC-DETAIL'in tip-spesifik açıklamasında yeni tip referansı.             |
| `docs/10_IMPLEMENTATION_ROADMAP.md` | Yeni süreç için faz numarası (örn. Faz 13) ekle.                                                                                                      |
| `docs/00_PROJECT_OVERVIEW.md`       | "Domain terminolojisi" bölümüne yeni terim varsa ekle.                                                                                                |
| `docs/adr/0XYZ-<slug>.md`           | **Sadece pattern'den sapma varsa** ADR yaz. KTİ pattern'ine tamamen uyuyorsa atla.                                                                    |

---

## 2. Cursor Rule — Phase File

| Dosya                                      | Açıklama                                                                                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `.cursor/rules/<NN>-phase-<XX>-<slug>.mdc` | Faz tanımı. NN = sıradaki numara (mevcut max'a +1; bkz. `ls .cursor/rules/`). Şablon: bu skill'in `phase-template.md` dosyası. |

---

## 3. Database (Faz "Geliştirme — DB")

| Dosya                                                                          | Değişiklik                                                                                                        |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `apps/api/prisma/schema.prisma`                                                | `enum ProcessType` içine yeni değer ekle. **Diğer modeller değişmez** — `process_type` zaten generic.             |
| `apps/api/prisma/migrations/<timestamp>_add_<slug>_process_type/migration.sql` | İki adım: `ALTER TYPE "ProcessType" ADD VALUE '<NEW_ENUM>'` + `CREATE SEQUENCE process_seq_<snake_case>` START 1. |

### KTİ baseline (referans)

```sql
-- apps/api/prisma/migrations/20260425120000_add_workflow_processes/migration.sql
CREATE SEQUENCE "process_seq_before_after_kaizen" START 1;
```

`schema.prisma` enum:

```prisma
enum ProcessType {
  BEFORE_AFTER_KAIZEN
  // YENİ tip buraya
}
```

---

## 4. Shared Packages (Faz "Geliştirme — Schemas/Types")

### 4.1 `packages/shared-types/src/permission.ts`

KTİ'de var: `PROCESS_KTI_START`. Yeni tip için aynı kalıp:

```typescript
// Permission enum'a ekle
PROCESS_<TIP>_START = 'PROCESS_<TIP>_START',

// PERMISSION_METADATA'ya ekle
[Permission.PROCESS_<TIP>_START]: {
  key: Permission.PROCESS_<TIP>_START,
  category: 'ACTION',
  description: '<TR ad> süreci başlatma',
  isSensitive: false,
},
```

**Test güncelle:** `packages/shared-types/src/permission.test.ts` enum count assertion'larını güncelle.

### 4.2 `packages/shared-schemas/src/processes.schemas.ts`

- `PROCESS_TYPE_FILTER` array'ine yeni enum ekle (`['BEFORE_AFTER_KAIZEN', '<NEW_ENUM>']`).
- Yeni `<Slug>StartBodySchema` ekle (KTİ'deki `KtiStartBodySchema` formatı). Mutlaka `.strict()`.
- `<Slug>StartInput` tipini export et.

**Test:** `processes.schemas.test.ts` varsa happy + fail case ekle.

### 4.3 `packages/shared-schemas/src/index.ts`

Yeni şemaları/tipleri re-export et.

---

## 5. Backend — Processes Modülü

### 5.1 Workflow sınıfı (yeni dosya)

`apps/api/src/processes/workflows/<slug>.workflow.ts` — KTİ workflow şablonu:

```typescript
import { Injectable } from '@nestjs/common';
import { ProcessType, type Task, type TaskStatus } from '@leanmgmt/prisma-client';
import { type ProcessAssigneeContext, type ProcessStepDefinition, type ProcessWorkflow } from './base-workflow.interface.js';
import { ProcessRollbackInvalidTargetException } from '../processes.exceptions.js';

const STEPS: readonly ProcessStepDefinition[] = [
  { order: 1, stepKey: '<TIP>_INITIATION', slaHours: 48 },
  { order: 2, stepKey: '<TIP>_<NEXT>', slaHours: 72 },
  // ...
];

@Injectable()
export class <Slug>Workflow implements ProcessWorkflow {
  readonly processType: ProcessType = '<NEW_ENUM>';

  getOrderedSteps() { return STEPS; }
  getStepByOrder(order: number) { /* like KTI */ }
  isCancelableProcessStatus(status: string): boolean { /* like KTI */ }
  isRollbackableProcessStatus(status: string): boolean { /* like KTI */ }
  findCurrentActiveStepOrder(tasks) { /* like KTI */ }
  assertRollbackTarget(args) { /* like KTI */ }
  resolveAssigneeUserIdForStep(step, context) {
    // Buradaki mapping → şablonun §3.2 "Assignee Kaynak" sütunundan gelir
  }
  getListActiveStepLabel(activeStepKey, processStatus) {
    // Şablonun §4.3 "Read Model" tablosundan gelir
  }
}
```

**Test:** `<slug>.workflow.test.ts` — KTİ test dosyası şablonu (`kti.workflow.test.ts`).

### 5.2 Registry'e kayıt

`apps/api/src/processes/process-type-registry.service.ts`:

```typescript
constructor(
  @Inject(KtiWorkflow) private readonly ktiWorkflow: KtiWorkflow,
  @Inject(<Slug>Workflow) private readonly <slug>Workflow: <Slug>Workflow,  // YENİ
) {}

onModuleInit(): void {
  this.register(this.ktiWorkflow.processType, this.ktiWorkflow);
  this.register(this.<slug>Workflow.processType, this.<slug>Workflow);  // YENİ
}
```

`apps/api/src/processes/processes.module.ts`:

```typescript
providers: [..., KtiWorkflow, <Slug>Workflow],
```

### 5.3 Service — start metodu

`apps/api/src/processes/processes.service.ts`:

- `startKti` metodunun yanına `start<Slug>(dto, actor)` ekle.
- Adımlar:
  1. Starter user lookup (manager_user_id varsa kontrol et)
  2. Doküman varsa `documentsService.assertCleanAndOwned(...)` (KTİ'de `assertKtiPhotoDocumentsCleanAndOwned`)
  3. `processTypeRegistry.getWorkflow(ProcessType.<NEW_ENUM>)`
  4. `nextval('process_seq_<slug>')` ile `displayId = <PREFIX>-NNNNNN`
  5. `prisma.$transaction`: process insert + initiation task `COMPLETED` + sonraki task `PENDING` + assignee insert
  6. Audit event emit (`task.assigned`)

**Yeni exception'lar:** `processes.exceptions.ts`'e ekle. Örn: `<Slug>CompanyMismatchException`, `<Slug>ManagerRequiredException` (KTİ'deki kalıp).

### 5.4 Controller — endpoint

`apps/api/src/processes/processes.controller.ts`:

```typescript
@Post('<slug>/start')
@HttpCode(HttpStatus.CREATED)
@RequirePermission(Permission.PROCESS_<TIP>_START)
@Throttle({ default: { limit: 10, ttl: 60_000 } })
@Audit('START_PROCESS', 'process')
async start<Slug>(
  @Body(createZodValidationPipe(<Slug>StartBodySchema)) body: <Slug>StartInput,
  @CurrentUser() actor: AuthenticatedUser,
) {
  return this.processesService.start<Slug>(body, actor);
}
```

**Test:** `apps/api/test/processes-<slug>.integration.test.ts`.

---

## 6. Backend — Tasks Modülü (KRİTİK BOŞLUK)

`apps/api/src/tasks/tasks.service.ts` — `complete()` metodunda şu an `BEFORE_AFTER_KAIZEN` guard'ı var:

```typescript
if (process.processType !== 'BEFORE_AFTER_KAIZEN') {
  throw new KtiNotSupportedException();
}
```

**İki yol var, sırayla değerlendir:**

### Yol A — Hızlı geçiş (yeni tip + KTİ destekle)

Guard'ı genişlet:

```typescript
const SUPPORTED: ProcessType[] = ['BEFORE_AFTER_KAIZEN', '<NEW_ENUM>'];
if (!SUPPORTED.includes(process.processType)) throw new ...;
```

Sonra `complete<Slug>Manager`, `complete<Slug>Revision` benzeri handler'lar yaz (KTİ'deki `completeKtiManager` örneğine bak).

### Yol B — Doğru pattern (registry-tabanlı)

`base-workflow.interface.ts`'e yeni method ekle:

```typescript
applyCompletion(
  tx: PrismaTx,
  task: Task,
  process: Process,
  action: string,
  formData: unknown,
): Promise<{ nextStep: ProcessStepDefinition | null; processStatus: string }>;
```

Her workflow bu metodu implement eder. `TasksService.complete()` registry üzerinden çağırır.

**Skill önerisi:** İlk yeni tip eklerken **Yol A** ile başla; ikinci tip eklerken refactor ederek **Yol B**'ye geç. Refactor sırasında `44-refactor-to-pattern.mdc` kuralını uygula.

### 6.1 Step labels

`apps/api/src/tasks/...` — KTİ task action mapping nerede tanımlıysa (örn. `kti-task-step.ts`) yeni step_key'leri map'le.

---

## 7. Seed (`apps/api/prisma/seed.ts`)

- `ALL_PERMISSION_KEYS` array'ine yeni permission(lar) ekle.
- Sistem rollerine atama: `assignPermissionsToRole(SUPERADMIN_ROLE, ALL_PERMISSION_KEYS)` zaten otomatik kapsar. Diğer roller (EMPLOYEE, MANAGER vb.) için açıkça ekle.
- (Opsiyonel) Dev/staging için demo süreç insert et.

---

## 8. Frontend

### 8.1 Route + Sayfa

`apps/web/src/app/(app)/processes/<slug>/start/page.tsx` — KTİ start sayfası şablonu:
`apps/web/src/app/(app)/processes/kti/start/page.tsx`.

### 8.2 Form bileşeni

`apps/web/src/components/processes/<Slug>StartForm.tsx` — `KtiStartForm.tsx` şablonu. Çok adımlı (bilgi → gözden geçir → ONAYLIYORUM kutusu).

### 8.3 Mutation hook

`apps/web/src/lib/queries/processes.ts` — yeni `useStart<Slug>` mutation ekle. KTİ start mutation şablon.

### 8.4 Sidebar menü

`apps/web/src/components/layout/AppSidebarNav.tsx` — `PermissionGate permission="PROCESS_<TIP>_START"` ile yeni link ekle.

### 8.5 Step labels (frontend)

`apps/web/src/lib/step-labels.ts` — yeni step_key → TR etiket eşleşmesi.

### 8.6 Liste filtresi

`apps/web/src/components/processes/ProcessList.tsx` + `ProcessAdminList.tsx` — `processType` dropdown'una yeni seçenek.

### 8.7 Breadcrumb regex

`apps/web/src/lib/app-breadcrumbs.ts` (veya benzeri) — `DISPLAY_ID_RE` regex'ini `/^(KTI|<PREFIX>)-\d{6}$/` olacak şekilde genişlet.

### 8.8 Task aksiyon UI

`apps/web/src/components/tasks/TaskActions.tsx` + `TaskDetail.tsx` — yeni step_key'ler için action butonları + form alanları.

---

## 9. Bildirimler / E-posta

### 9.1 Domain events (`apps/api/src/notifications/notification-domain.events.ts`)

Genelde event tipleri jenerik (`task.assigned`, `task.completed`). Yeni event eklenmez **eğer** ekran katalogunda yeni bildirim türü yoksa.

### 9.2 E-posta şablonları

`apps/api/src/email-templates/` (veya admin panel) — şablonun §6.2 tablosundaki yeni template'leri:

- Template key
- Subject TR
- Body TR (markdown + handlebars)
- Test send dev seed'de

---

## 10. Test'ler

| Test türü              | Konum                                                              | Coverage hedef   |
| ---------------------- | ------------------------------------------------------------------ | ---------------- |
| Workflow unit          | `apps/api/src/processes/workflows/<slug>.workflow.test.ts`         | ≥85% line        |
| Service unit           | `apps/api/src/processes/processes.service.test.ts` (genişlet)      | ≥80% line        |
| Controller integration | `apps/api/test/processes-<slug>.integration.test.ts`               | happy + 4-5 edge |
| Schema unit            | `packages/shared-schemas/src/processes.schemas.test.ts` (genişlet) | sınır            |
| Frontend smoke         | `apps/web/test/processes-<slug>-start.spec.ts` (Playwright)        | happy            |

---

## 11. Yeniden Kullanılan Bileşenler (DEĞİŞTİRME!)

- `PROCESS_CANCEL`, `PROCESS_ROLLBACK`, `PROCESS_VIEW_ALL`, `DOCUMENT_UPLOAD` permission'ları
- `ProcessesController`'daki `list`, `detail`, `cancel`, `rollback` route'ları (jenerik)
- `ProcessList` / `ProcessDetail` / `ProcessTimeline` / `TaskHistoryTimeline` bileşenleri
- `DocumentUpload` bileşeni
- SLA overdue cron (`task.sla.overdue` event'i)
- Audit log altyapısı
- Notifications + email worker pipeline (Faz 7)

---

## 12. Doğrulama Sırası

```
1. pnpm --filter @leanmgmt/shared-types test
2. pnpm --filter @leanmgmt/shared-schemas test
3. pnpm --filter api prisma migrate dev
4. pnpm --filter api test               # unit
5. pnpm --filter api test:int           # integration
6. pnpm --filter web test               # unit
7. pnpm --filter web test:e2e           # smoke (yalnız happy)
8. pnpm lint && pnpm typecheck
```

Tüm adımlar green → faz human gate'e geçer.

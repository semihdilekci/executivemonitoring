import type { UserRole } from "./models";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  statusCode: number;
}

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    "statusCode" in error
  );
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    email: string;
    full_name: string;
    role: UserRole;
  };
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserMeResponse {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export type DigestStatus = "generating" | "ready" | "failed";

export interface DigestListItem {
  id: string;
  /** Serbest bülten slug'ı (Faz 6.5 — `digest_type` enum kaldırıldı). */
  newsletter_slug: string;
  title: string;
  status: DigestStatus;
  period_start: string;
  period_end: string;
  total_sources_used: number;
  created_at: string;
  completed_at: string | null;
  /** Backend read endpoint hazır olduğunda API'den gelir. */
  is_read?: boolean;
}

export interface PaginationMeta {
  next_cursor: string | null;
  has_more: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationMeta;
}

export interface BriefStats {
  source_count: number;
  new_digest_count: number;
  processed_news_count: number;
  yildiz_impact_count: number;
}

export interface TodayBrief {
  summary: string;
  stats: BriefStats;
  generated_at: string;
}

export interface DigestListParams {
  cursor?: string;
  limit?: number;
  newsletter_slug?: string;
  status?: DigestStatus;
  is_read?: boolean;
}

export interface SourceReference {
  processed_item_id: string;
  title: string;
  url: string | null;
  /** Kaynak haberin en fazla iki cümlelik özeti (Faz 6.5). Eski bültenlerde olmayabilir. */
  summary?: string | null;
  /** RSS/API/e-posta kaynağının görünen adı. */
  source_name?: string | null;
  /** Haberin yayın tarihi (ISO 8601). */
  published_at?: string | null;
}

export interface DigestSection {
  id: string;
  section_order: number;
  section_title: string;
  ai_summary: string;
  impact_note: string | null;
  source_references: SourceReference[];
}

export interface DigestDetail extends DigestListItem {
  /** Editör LLM tarafından üretilen haftalık bülten özeti (Faz 6.5). */
  summary: string | null;
  sections: DigestSection[];
}

export interface NewsImpactRequest {
  processed_item_id: string;
}

export interface NewsImpactResponse {
  analysis: string;
}

export interface ChatSource {
  chunk_id: string;
  processed_item_id: string;
  title: string;
  url: string | null;
  score: number;
}

export interface ChatAskResponse {
  answer: string;
  sources: ChatSource[];
  model: string;
  tokens_used: number;
}

export interface ChatAskRequest {
  question: string;
  digest_id?: string;
}

export interface UserListItem {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserListParams {
  cursor?: string;
  limit?: number;
  role?: UserRole;
  is_active?: boolean;
}

export interface CreateUserRequest {
  email: string;
  full_name: string;
  role: UserRole;
  password: string;
}

export interface UpdateUserRequest {
  full_name?: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface PasswordResetInitiateRequest {
  user_id: string;
}

export interface PasswordResetInitiateResponse {
  message: string;
  expires_at: string;
}

export type SourceType =
  | "rss"
  | "email"
  | "rest_api"
  | "websocket"
  | "gov";

export type SourceStatus = "active" | "inactive" | "error";

export type SourceCategory =
  | "macro"
  | "finance"
  | "fmcg"
  | "strategy"
  | "geopolitical"
  | "regulatory";

export interface SourceListItem {
  id: string;
  name: string;
  source_type: SourceType;
  config: Record<string, unknown>;
  polling_interval_minutes: number;
  status: SourceStatus;
  last_fetched_at: string | null;
  error_count: number;
  category: SourceCategory;
  target_phase: string;
  created_at: string;
  updated_at: string;
}

export interface SourceListParams {
  cursor?: string;
  limit?: number;
  source_type?: SourceType;
  status?: SourceStatus;
  category?: SourceCategory;
  q?: string;
}

export interface CreateSourceRequest {
  name: string;
  source_type: SourceType;
  config: Record<string, unknown>;
  polling_interval_minutes: number;
  category: SourceCategory;
  target_phase: string;
}

export interface UpdateSourceRequest {
  name?: string;
  config?: Record<string, unknown>;
  polling_interval_minutes?: number;
  category?: SourceCategory;
  target_phase?: string;
}

export interface PatchSourceStatusRequest {
  status: SourceStatus;
}

export interface DeleteSourceResponse {
  message: string;
  deleted_raw_items_count: number;
}

export type ApiProvider = "groq" | "gemini" | "anthropic";

/**
 * Bülten şablonu (newsletter template) — iki seviyeli serbest model (Faz 6.5).
 * Eski `PromptTemplate*` tipleri ADR-0003 ile kaldırıldı.
 */
export interface NewsletterSection {
  id: string;
  name: string;
  sort_order: number;
  section_system_prompt: string;
  section_user_prompt: string;
  impact_prompt: string;
  is_active: boolean;
}

export interface NewsletterTemplate {
  id: string;
  slug: string;
  name: string;
  description: string;
  date_range_days: number;
  summary_system_prompt: string;
  summary_user_prompt: string;
  min_content_score: number;
  /** Bülten-bazı içerik kategori ön-filtresi; boş = tüm kategoriler. */
  content_categories: ContentCategory[];
  model_preference: string | null;
  is_active: boolean;
  sections: NewsletterSection[];
  created_at: string;
  updated_at: string;
}

export interface NewsletterTemplateListResponse {
  data: NewsletterTemplate[];
}

/** Oluştur/güncelle isteğindeki bölüm — `id` verilirse mevcut bölüm güncellenir. */
export interface NewsletterSectionInput {
  id?: string | null;
  name: string;
  sort_order: number;
  section_system_prompt: string;
  section_user_prompt: string;
  impact_prompt: string;
  is_active: boolean;
}

export interface CreateNewsletterTemplateRequest {
  slug: string;
  name: string;
  description: string;
  date_range_days: number;
  summary_system_prompt: string;
  summary_user_prompt: string;
  min_content_score: number;
  content_categories: ContentCategory[];
  model_preference: string | null;
  is_active: boolean;
  sections: NewsletterSectionInput[];
}

/** Güncelleme isteği — `slug` değiştirilemez (benzersiz, salt-okunur). */
export type UpdateNewsletterTemplateRequest = Omit<
  CreateNewsletterTemplateRequest,
  "slug"
>;

/** LLM operasyon tipi — `request_type_scope` üyeleri (`Docs/03` §6). */
export type LlmRequestType =
  | "digest_generation"
  | "chatbot"
  | "article_translation";

export interface ApiKeyItem {
  id: string;
  provider: ApiProvider;
  key_alias: string;
  model: string | null;
  is_active: boolean;
  priority_order: number;
  /** Faz 6.5: anahtarın kullanılacağı operasyonlar; `[]` = tüm operasyonlar. */
  request_type_scope: LlmRequestType[];
  created_at: string;
  /** Backend mask desteği geldiğinde son 4 karakter. */
  key_suffix?: string | null;
}

export interface ApiKeyListResponse {
  data: ApiKeyItem[];
}

export interface CreateApiKeyRequest {
  provider: ApiProvider;
  key_alias: string;
  api_key: string;
  model: string;
  priority_order: number;
  is_active?: boolean;
  request_type_scope?: LlmRequestType[];
}

export interface PatchApiKeyStatusRequest {
  is_active: boolean;
}

export interface UpdateApiKeyRequest {
  request_type_scope: LlmRequestType[];
  model?: string;
}

export interface DeleteApiKeyResponse {
  message: string;
}

export type UsageStatsPeriod = "daily" | "weekly" | "monthly";

export interface RequestTypeStats {
  requests: number;
  tokens: number;
}

export interface UsageStatsRow {
  date: string;
  provider: ApiProvider;
  api_key_alias: string;
  total_requests: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  avg_latency_ms: number | null;
  error_count: number;
  by_request_type: Record<string, RequestTypeStats>;
}

export interface ApiUsageStatsResponse {
  period: UsageStatsPeriod;
  data: UsageStatsRow[];
}

export interface ApiUsageStatsParams {
  period?: UsageStatsPeriod;
  provider?: ApiProvider;
  api_key_id?: string;
  start_date?: string;
  end_date?: string;
}

export interface AuditLogItem {
  id: string;
  event_type: string;
  actor_user_id: string | null;
  actor_name: string | null;
  target_type: string | null;
  target_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListParams {
  cursor?: string;
  limit?: number;
  event_type?: string;
  actor_user_id?: string;
  target_type?: string;
  start_date?: string;
  end_date?: string;
}

export interface ChatHistoryItem {
  id: string;
  user_id: string;
  user_name: string;
  question: string;
  answer: string;
  sources: ChatSource[];
  tokens_used: number;
  model: string;
  created_at: string;
}

export interface ChatHistoryListParams {
  cursor?: string;
  limit?: number;
  user_id?: string;
  start_date?: string;
  end_date?: string;
}

export interface NotificationPreferenceItem {
  user_id: string;
  user_name: string;
  email_enabled: boolean;
  push_enabled: boolean;
  has_fcm_token: boolean;
}

export interface NotificationPreferenceListResponse {
  data: NotificationPreferenceItem[];
}

export interface UpdateNotificationPreferenceRequest {
  email_enabled: boolean;
  push_enabled: boolean;
}

export type NotificationRecipientType = "digest" | "error_alert";

export interface NotificationRecipientItem {
  id: string;
  user_id: string;
  user_name: string;
  email: string;
  types: NotificationRecipientType[];
}

export interface NotificationRecipientListResponse {
  data: NotificationRecipientItem[];
}

export interface CreateNotificationRecipientRequest {
  user_id: string;
  types: NotificationRecipientType[];
}

export interface NotificationScheduleEntry {
  day: string;
  time: string;
  enabled: boolean;
}

export type NotificationScheduleConfig = Record<
  string,
  NotificationScheduleEntry
>;

export interface SettingItem {
  key: string;
  value: unknown;
  description: string | null;
  updated_at: string;
  warning?: string | null;
}

export interface SettingListResponse {
  data: SettingItem[];
}

export interface UpdateSettingRequest {
  value: unknown;
}

export interface SettingUpdateResponse extends SettingItem {
  warning?: string | null;
}

// --- Pipeline Monitoring (Faz 6.1) — `Docs/03` §11.5 ---

export type PipelineRunType = "collect_pipeline" | "digest_update";

export type PipelineRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled";

export type PipelineStage = "collect" | "ingest" | "process" | "digest";

export type PipelineStepStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export interface PipelineStep {
  stage: PipelineStage;
  status: PipelineStepStatus;
  sequence: number;
  items_in: number;
  items_out: number;
  items_failed: number;
  detail: Record<string, unknown>;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface PipelineRunSummary {
  id: string;
  run_type: PipelineRunType;
  status: PipelineRunStatus;
  source_types: string[];
  stats: Record<string, unknown>;
  triggered_by_name: string | null;
  current_stage: PipelineStage | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface PipelineRunDetail extends PipelineRunSummary {
  params: Record<string, unknown>;
  error_summary: string | null;
  steps: PipelineStep[];
}

// --- Run içerik kırılımı (Faz 6.3) — `Docs/03` §11.5 ---

/** Bir ham içeriğin run penceresindeki akıbeti. */
export type RunItemOutcome = "processed" | "filtered" | "failed";

export interface RunItem {
  id: string;
  source_id: string;
  source_name: string;
  title: string | null;
  url: string | null;
  snippet: string;
  outcome: RunItemOutcome;
  content_category: ContentCategory | null;
  relevance_score: number | null;
  fetched_at: string;
}

export interface RunSourceBreakdown {
  source_id: string;
  source_name: string;
  collected: number;
  processed: number;
  filtered: number;
  failed: number;
}

export interface RunItemsResponse {
  collected: number;
  processed: number;
  filtered: number;
  failed: number;
  by_source: RunSourceBreakdown[];
  items: RunItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface RunItemsParams {
  outcome?: RunItemOutcome;
  page?: number;
  page_size?: number;
}

export interface PipelineRunListParams {
  cursor?: string;
  limit?: number;
  run_type?: PipelineRunType;
  status?: PipelineRunStatus;
  start_date?: string;
  end_date?: string;
}

export interface TriggerCollectPipelineRequest {
  run_type: "collect_pipeline";
  source_types: string[];
}

export interface TriggerDigestUpdateRequest {
  run_type: "digest_update";
  newsletter_template_id: string;
  period_start: string;
  period_end: string;
  send_notification: boolean;
}

export type TriggerPipelineRequest =
  | TriggerCollectPipelineRequest
  | TriggerDigestUpdateRequest;

export interface TriggerPipelineResponse {
  id: string;
  run_type: PipelineRunType;
  status: PipelineRunStatus;
  message: string;
}

export interface CancelPipelineResponse {
  id: string;
  status: PipelineRunStatus;
}

// --- İçerik Arşivi (Faz 6.2) — `Docs/03` §11.6 ---

export type SchemaCategory = "news" | "market" | "geo" | "transport" | "fmcg";

export type ContentCategory =
  | "macro"
  | "fmcg"
  | "finance"
  | "geopolitical"
  | "strategy"
  | "regulatory";

export interface DigestUsageSummary {
  digest_id: string;
  newsletter_slug: string;
  digest_title: string;
  period_start: string;
  period_end: string;
}

export interface DigestUsageDetail extends DigestUsageSummary {
  section_title: string;
}

export interface ProcessedItemListItem {
  id: string;
  schema_category: SchemaCategory;
  content_category: ContentCategory | null;
  source_id: string;
  source_name: string;
  source_type: SourceType;
  title: string;
  url: string | null;
  language: string;
  relevance_score: number;
  topics: string[];
  published_at: string | null;
  processed_at: string;
  digest_usages: DigestUsageSummary[];
}

export interface ProcessedItemDetail {
  id: string;
  schema_category: SchemaCategory;
  content_category: ContentCategory | null;
  source_id: string;
  source_name: string;
  source_type: SourceType;
  title: string;
  url: string | null;
  clean_content: string;
  summary: string | null;
  language: string;
  /** Faz 6.5: canonical olmayan dil varyantları (orijinal EN vb.); TR kaynaklıda boş. */
  translations: TranslationVariant[];
  relevance_score: number;
  topics: string[];
  entities: unknown[];
  published_at: string | null;
  processed_at: string;
  chunk_count: number;
  digest_usages: DigestUsageDetail[];
}

export interface TranslationVariant {
  language: string;
  title: string;
  content: string;
  is_original: boolean;
}

export type ProcessedItemSortField =
  | "processed_at"
  | "published_at"
  | "relevance_score"
  | "title";

export type SortDirection = "asc" | "desc";

export interface ProcessedItemListParams {
  cursor?: string;
  limit?: number;
  source_id?: string;
  schema_category?: SchemaCategory;
  content_category?: ContentCategory;
  published_from?: string;
  published_to?: string;
  min_score?: number;
  topic?: string;
  q?: string;
  has_digest?: boolean;
  sort_by?: ProcessedItemSortField;
  sort_dir?: SortDirection;
}

// --- Keyword Takibi (Faz 6.3) — `Docs/03` §11.7 ---

/**
 * Keyword havuzu kategori enum'u (`keyword_category_enum`). Değerler
 * `content_category` ile birebir aynı (`Docs/02` §3) — alias kullanılır.
 */
export type KeywordCategory = ContentCategory;

export interface KeywordCategoryRating {
  category: KeywordCategory;
  rating: number;
}

export interface KeywordResponse {
  id: string;
  term_tr: string;
  term_en: string;
  is_active: boolean;
  categories: KeywordCategoryRating[];
  created_at: string;
  updated_at: string;
}

/** Offset pagination meta — keyword havuzu küçük olduğu için cursor kullanılmaz. */
export interface KeywordPaginationMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface KeywordListResponse {
  data: KeywordResponse[];
  pagination: KeywordPaginationMeta;
}

export interface KeywordListParams {
  category?: KeywordCategory;
  q?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export interface KeywordCreateRequest {
  term_tr: string;
  term_en: string;
  is_active: boolean;
  categories: KeywordCategoryRating[];
}

/** Kısmi güncelleme — `categories` verilirse tam set (replace semantiği). */
export interface KeywordUpdateRequest {
  term_tr?: string;
  term_en?: string;
  is_active?: boolean;
  categories?: KeywordCategoryRating[];
}

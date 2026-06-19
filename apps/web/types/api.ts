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

export type DigestType =
  | "turkish_media_weekly"
  | "fmcg_weekly"
  | "strategy_weekly";

export type DigestStatus = "generating" | "ready" | "failed";

export interface DigestListItem {
  id: string;
  digest_type: DigestType;
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
  digest_type?: DigestType;
  status?: DigestStatus;
  is_read?: boolean;
}

export interface SourceReference {
  processed_item_id: string;
  title: string;
  url: string | null;
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
  sections: DigestSection[];
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
  | "turkish_media"
  | "fmcg"
  | "strategy"
  | "official"
  | "market"
  | "geo"
  | "transport";

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

export type ApiProvider = "groq" | "gemini";

export interface PromptTemplateItem {
  id: string;
  name: string;
  digest_type: DigestType;
  section_key: string;
  system_prompt: string;
  user_prompt_template: string;
  model_preference: ApiProvider | null;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateListResponse {
  data: PromptTemplateItem[];
}

export interface CreatePromptTemplateRequest {
  name: string;
  digest_type: DigestType;
  section_key: string;
  system_prompt: string;
  user_prompt_template: string;
  model_preference?: ApiProvider | null;
  is_active?: boolean;
}

export interface UpdatePromptTemplateRequest {
  name: string;
  digest_type: DigestType;
  section_key: string;
  system_prompt: string;
  user_prompt_template: string;
  model_preference?: ApiProvider | null;
  is_active: boolean;
}

export interface ApiKeyItem {
  id: string;
  provider: ApiProvider;
  key_alias: string;
  is_active: boolean;
  priority_order: number;
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
  priority_order: number;
  is_active?: boolean;
}

export interface PatchApiKeyStatusRequest {
  is_active: boolean;
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

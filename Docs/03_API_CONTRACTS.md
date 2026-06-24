# 03 — API Contracts

## 1. Genel İlkeler

| İlke | Değer |
|------|-------|
| Base URL | `/api/v1/` |
| Protokol | HTTPS zorunlu; HTTP → HTTPS yönlendirmesi aktif |
| Content-Type | `application/json` (tüm request ve response body'leri) |
| Auth Header | `Authorization: Bearer <access_token>` |
| Dil | Hata mesajları ve kullanıcıya dönük metinler Türkçe |
| Framework | FastAPI (Python) — otomatik OpenAPI/Swagger (`/api/v1/docs`) |
| Validation | Pydantic model ile request body doğrulaması |
| ORM | SQLAlchemy parametrik sorgu; raw SQL yasak |
| Versioning | URL prefix (`/api/v1/`). Major versiyon değişikliğinde `/api/v2/` açılır, v1 minimum 6 ay korunur |

Tüm endpoint'ler aksi belirtilmedikçe `Authorization: Bearer <access_token>` header'ı gerektirir. Auth gerektirmeyen endpoint'ler açıkça işaretlenmiştir.

---

## 2. Kimlik Doğrulama Endpoint'leri

### POST /api/v1/auth/login _(Auth gerektirmez)_

Kullanıcı girişi. Başarılı girişte access token + refresh token döner.

**Request:**
```json
{
  "email": "kullanici@yildizholding.com",
  "password": "Parola123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "kullanici@yildizholding.com",
    "full_name": "Ali Yılmaz",
    "role": "viewer"
  }
}
```

**Hata durumları:**

| Status | Kod | Durum |
|--------|-----|-------|
| 401 | `AUTH_INVALID_CREDENTIALS` | E-posta veya şifre hatalı |
| 403 | `AUTH_ACCOUNT_INACTIVE` | Kullanıcı pasif (`is_active = false`) |
| 429 | `RATE_LIMIT_EXCEEDED` | Login rate limit aşıldı (10 req/dk per IP) |

Login başarılı olduğunda `audit_logs` tablosuna `user.login` olayı yazılır. `last_login_at` güncellenir.

### POST /api/v1/auth/refresh _(Auth gerektirmez)_

Refresh token ile yeni access token üretir.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOi..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Hata durumları:**

| Status | Kod | Durum |
|--------|-----|-------|
| 401 | `AUTH_INVALID_REFRESH_TOKEN` | Token geçersiz veya süresi dolmuş |
| 403 | `AUTH_ACCOUNT_INACTIVE` | Kullanıcı pasif — refresh reddedilir |

Pasif kullanıcının mevcut access token'ı süresi dolana kadar geçerli kalır ancak refresh yapılamaz.

### POST /api/v1/auth/logout

Mevcut oturumu sonlandırır. Refresh token invalidate edilir.

**Request:** Body yok.

**Response (200):**
```json
{
  "message": "Oturum sonlandırıldı."
}
```

Audit log'a `user.logout` olayı yazılır.

### POST /api/v1/auth/password-reset/initiate _(Admin only)_

Admin tarafından kullanıcıya şifre sıfırlama link'i gönderir.

**Request:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (200):**
```json
{
  "message": "Şifre sıfırlama bağlantısı kullanıcıya e-posta ile gönderildi.",
  "expires_at": "2026-06-17T12:00:00Z"
}
```

Tek kullanımlık token üretilir, bcrypt hash'lenerek `password_reset_tokens` tablosuna yazılır. Token 24 saat geçerlidir. Kullanıcıya e-posta ile reset link'i gönderilir. Audit log'a `password.reset_initiated` yazılır.

### POST /api/v1/auth/password-reset/complete _(Auth gerektirmez)_

Kullanıcı reset link'indeki token ile yeni şifre belirler.

**Request:**
```json
{
  "token": "abc123def456...",
  "new_password": "YeniParola456"
}
```

**Response (200):**
```json
{
  "message": "Şifre başarıyla güncellendi."
}
```

**Hata durumları:**

| Status | Kod | Durum |
|--------|-----|-------|
| 400 | `PASSWORD_POLICY_VIOLATION` | Şifre politikasına uymayan (min 8 karakter, 1 büyük harf, 1 rakam) |
| 401 | `AUTH_INVALID_RESET_TOKEN` | Token geçersiz, süresi dolmuş veya daha önce kullanılmış |

Token kullanıldıktan sonra `used_at` alanı doldurulur ve tekrar kullanılamaz.

---

## 3. Kullanıcı Yönetimi Endpoint'leri

### GET /api/v1/users _(Admin only)_

Tüm kullanıcıları listeler.

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `cursor` | string | Hayır | Pagination cursor (son kullanıcının ID'si) |
| `limit` | integer | Hayır | Sayfa boyutu (varsayılan: 20, max: 50) |
| `role` | string | Hayır | Rol filtresi (`admin` \| `viewer`) |
| `is_active` | boolean | Hayır | Aktiflik filtresi |

**Response (200):**
```json
{
  "data": [
    {
      "id": "550e8400-...",
      "email": "ali@yildizholding.com",
      "full_name": "Ali Yılmaz",
      "role": "viewer",
      "is_active": true,
      "created_at": "2026-06-01T10:00:00Z",
      "last_login_at": "2026-06-15T08:30:00Z"
    }
  ],
  "pagination": {
    "next_cursor": "660e8400-...",
    "has_more": true
  }
}
```

### POST /api/v1/users _(Admin only)_

Yeni kullanıcı oluşturur.

**Request:**
```json
{
  "email": "yeni@yildizholding.com",
  "full_name": "Ayşe Demir",
  "role": "viewer",
  "password": "GeciciSifre1"
}
```

**Response (201):**
```json
{
  "id": "770e8400-...",
  "email": "yeni@yildizholding.com",
  "full_name": "Ayşe Demir",
  "role": "viewer",
  "is_active": true,
  "created_at": "2026-06-16T10:00:00Z"
}
```

Kullanıcı oluşturulduğunda `notification_preferences` kaydı varsayılan değerlerle otomatik oluşturulur. Audit log'a `user.created` yazılır.

**Hata durumları:**

| Status | Kod | Durum |
|--------|-----|-------|
| 400 | `PASSWORD_POLICY_VIOLATION` | Şifre politikasına uymayan |
| 409 | `USER_EMAIL_EXISTS` | E-posta adresi zaten kayıtlı |

### GET /api/v1/users/{user_id} _(Admin only)_

Tek kullanıcı detayı. Response formatı listeleme ile aynıdır (tek obje, dizi değil).

### PUT /api/v1/users/{user_id} _(Admin only)_

Kullanıcı bilgilerini günceller.

**Request (kısmi güncelleme desteklenir):**
```json
{
  "full_name": "Ali Yılmaz (Güncel)",
  "role": "admin",
  "is_active": false
}
```

Rol değişikliğinde `user.role_changed`, pasif yapılmada `user.deactivated` audit log'a yazılır.

### GET /api/v1/users/me _(Admin + Viewer)_

Giriş yapmış kullanıcının kendi profili. Password hash dahil edilmez.

**Response (200):**
```json
{
  "id": "550e8400-...",
  "email": "ali@yildizholding.com",
  "full_name": "Ali Yılmaz",
  "role": "viewer",
  "is_active": true,
  "created_at": "2026-06-01T10:00:00Z",
  "last_login_at": "2026-06-15T08:30:00Z"
}
```

---

## 4. Kaynak (Source) Yönetimi Endpoint'leri

### GET /api/v1/sources _(Admin only)_

Tüm veri kaynaklarını listeler.

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `cursor` | string | Hayır | Pagination cursor |
| `limit` | integer | Hayır | Sayfa boyutu (varsayılan: 20, max: 100) |
| `source_type` | string | Hayır | Tip filtresi (`rss`, `email`, `rest_api`, `websocket`, `gov`) |
| `status` | string | Hayır | Durum filtresi (`active`, `inactive`, `error`) |
| `category` | string | Hayır | Kategori filtresi |

**Response (200):**
```json
{
  "data": [
    {
      "id": "880e8400-...",
      "name": "Bloomberg HT RSS",
      "source_type": "rss",
      "config": {"feed_url": "https://bloomberght.com/rss"},
      "polling_interval_minutes": 15,
      "status": "active",
      "last_fetched_at": "2026-06-16T09:45:00Z",
      "error_count": 0,
      "category": "turkish_media",
      "target_phase": "mvp-0",
      "created_at": "2026-06-01T10:00:00Z"
    }
  ],
  "pagination": {
    "next_cursor": "990e8400-...",
    "has_more": false
  }
}
```

### GET /api/v1/sources/{source_id} _(Admin only)_

Tek bir veri kaynağının detayını döner.

**Response (200):** `SourceResponse` — liste öğesi ile aynı alanlar (`id`, `name`, `source_type`, `config`, `polling_interval_minutes`, `status`, `last_fetched_at`, `error_count`, `category`, `target_phase`, `created_at`).

**Hatalar:**

| Kod | Durum |
|-----|-------|
| `NOT_FOUND` | Kaynak bulunamadı |
| `FORBIDDEN` | Admin değil |

### POST /api/v1/sources _(Admin only)_

Yeni veri kaynağı ekler.

**Request:**
```json
{
  "name": "Food Navigator RSS",
  "source_type": "rss",
  "config": {
    "feed_url": "https://foodnavigator.com/rss",
    "language": "en",
    "ingest_mode": "all",
    "default_category": "fmcg"
  },
  "polling_interval_minutes": 15,
  "category": "fmcg",
  "target_phase": "mvp-0"
}
```

**Config zorunlu alanlar (MVP-0):** `ingest_mode` (`"all"` | `"filtered"`), `default_category`. Tip-spesifik alanlar (`feed_url`, `imap_host`, vb.) collector tipine göre eklenir (`Docs/02` §4.2, `Docs/04` §8.3).

**Response (201):** Oluşturulan source objesi.

Audit log'a `source.created` yazılır.

### PUT /api/v1/sources/{source_id} _(Admin only)_

Kaynak güncelleme. Kısmi güncelleme desteklenir.

### DELETE /api/v1/sources/{source_id} _(Admin only)_

Kaynağı ve ilişkili tüm raw_items'ı siler (CASCADE). Bu işlem geri alınamaz.

**Response (200):**
```json
{
  "message": "Kaynak ve ilişkili veriler silindi.",
  "deleted_raw_items_count": 1250
}
```

Audit log'a `source.deleted` yazılır.

### PATCH /api/v1/sources/{source_id}/status _(Admin only)_

Kaynak durumunu değiştirir (active/inactive). Error state'ten çıkmak için de kullanılır.

**Request:**
```json
{
  "status": "active"
}
```

`error → active` geçişinde `error_count` sıfırlanır. Audit log'a `source.status_changed` yazılır.

---

## 5. Bülten Şablonu (Newsletter Template) Endpoint'leri

> **Faz 6.5:** Eski `/prompt-templates` endpoint'leri kaldırıldı. İki seviyeli serbest model (`newsletter_templates` + nested `newsletter_sections`). Tümü **Admin only**; state değişiminde audit (`newsletter_template.created/updated/deleted`). Şablon production'a almak kullanıcı onayı gerektirir.

### GET /api/v1/newsletter-templates _(Admin only)_

Tüm bültenleri listeler (bölümler dahil). Sayı sınırlı → pagination yok.

**Query:** `is_active` (boolean, opsiyonel).

**Response (200):**
```json
{
  "data": [
    {
      "id": "aa0e8400-...",
      "slug": "fmcg_weekly",
      "name": "FMCG Haftalık",
      "description": "Yıldız Holding ve FMCG sektörüyle ilgili haftalık bülten.",
      "date_range_days": 7,
      "summary_system_prompt": "Sen Yıldız Holding CEO'su gibi düşünen bir editörsün...",
      "summary_user_prompt": "Bülten: {newsletter_name}\nAçıklama: {newsletter_description}\nBölümler: {sections}\nHaberler:\n{articles}\n\nUygun haberleri bölümlere dağıt, alakasızı ele, haftalık özet yaz.",
      "min_content_score": 50,
      "model_preference": null,
      "is_active": true,
      "sections": [
        {
          "id": "bb1f9500-...",
          "name": "Yıldız ve Rakipleri",
          "sort_order": 1,
          "section_system_prompt": "Sen bir FMCG analistisin...",
          "section_user_prompt": "Bölüm: {section_name}\nHaberler:\n{articles}\n\nÖzet yaz.",
          "impact_prompt": "Bu haberlerin Yıldız Holding ve firmaları için etkisini analiz et.",
          "is_active": true
        }
      ],
      "created_at": "2026-06-01T10:00:00Z",
      "updated_at": "2026-06-10T14:30:00Z"
    }
  ]
}
```

**Prompt değişkenleri:** Editör (summary) prompt'u → `{newsletter_name}`, `{newsletter_description}`, `{date_range}`, `{sections}`, `{articles}`. Bölüm prompt'u → `{section_name}`, `{newsletter_name}`, `{date_range}`, `{articles}`.

### POST /api/v1/newsletter-templates _(Admin only)_

Yeni bülten oluşturur (bölümler nested). **Response (201):** oluşturulan obje.

**Request (özet):**
```json
{
  "slug": "tech_weekly",
  "name": "Teknoloji Haftalık",
  "description": "...",
  "date_range_days": 7,
  "summary_system_prompt": "...",
  "summary_user_prompt": "...",
  "min_content_score": 50,
  "model_preference": "gemini",
  "sections": [
    { "name": "Yapay Zekâ", "sort_order": 1, "section_system_prompt": "...", "section_user_prompt": "...", "impact_prompt": "..." }
  ]
}
```

**Hata kodları:** `slug` çakışması → 409 `NEWSLETTER_SLUG_EXISTS`; `min_content_score` 0–100 dışı veya boş bölüm listesi → 422.

### GET /api/v1/newsletter-templates/{id} _(Admin only)_

Tek bülten detayı (bölümler dahil).

### PUT /api/v1/newsletter-templates/{id} _(Admin only)_

Bülten + bölümleri günceller. Bölümler **replace** semantiği ile gönderilir (mevcut bölümler `id` ile eşleşir; eksikler silinir/deaktive, yeniler eklenir). Audit `newsletter_template.updated`.

### DELETE /api/v1/newsletter-templates/{id} _(Admin only)_

Bülteni siler. Bölümler CASCADE; geçmiş digest'ler `newsletter_slug` ile korunur (`newsletter_template_id` SET NULL). Audit `newsletter_template.deleted`.

---

## 6. API Key Yönetimi Endpoint'leri

### GET /api/v1/api-keys _(Admin only)_

LLM API key'lerini listeler. `encrypted_key` alanı response'ta dönmez; yalnızca `key_alias`, `provider`, `is_active`, `priority_order` görünür.

**Response (200):**
```json
{
  "data": [
    {
      "id": "bb0e8400-...",
      "provider": "groq",
      "key_alias": "Groq Primary",
      "is_active": true,
      "priority_order": 1,
      "created_at": "2026-06-01T10:00:00Z"
    }
  ]
}
```

### POST /api/v1/api-keys _(Admin only)_

Yeni API key ekler.

**Request:**
```json
{
  "provider": "gemini",
  "key_alias": "Gemini Backup",
  "api_key": "AIzaSy...",
  "priority_order": 2
}
```

`api_key` alanı şifrelenerek `encrypted_key` olarak saklanır. Response'ta plain-text key dönmez. Audit log'a `api_key.created` yazılır.

### DELETE /api/v1/api-keys/{key_id} _(Admin only)_

API key siler. İlişkili `api_usage_logs` kayıtları korunur (CASCADE ile silinir).

Audit log'a `api_key.deleted` yazılır.

### PATCH /api/v1/api-keys/{key_id}/status _(Admin only)_

Key aktif/pasif durumunu değiştirir.

**Request:**
```json
{
  "is_active": false
}
```

### GET /api/v1/api-keys/usage-stats _(Admin only)_

Token kullanım metrikleri. Admin panelindeki grafiklerin veri kaynağı.

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `period` | string | Hayır | `daily` \| `weekly` \| `monthly` (varsayılan: `daily`) |
| `provider` | string | Hayır | Provider filtresi |
| `api_key_id` | string | Hayır | Belirli key filtresi |
| `start_date` | date | Hayır | Başlangıç tarihi (varsayılan: 30 gün önce) |
| `end_date` | date | Hayır | Bitiş tarihi (varsayılan: bugün) |

**Response (200):**
```json
{
  "period": "daily",
  "data": [
    {
      "date": "2026-06-15",
      "provider": "groq",
      "api_key_alias": "Groq Primary",
      "total_requests": 45,
      "total_prompt_tokens": 125000,
      "total_completion_tokens": 38000,
      "total_tokens": 163000,
      "avg_latency_ms": 1250,
      "error_count": 2,
      "by_request_type": {
        "digest_generation": {"requests": 12, "tokens": 98000},
        "chatbot": {"requests": 30, "tokens": 55000},
        "summary": {"requests": 3, "tokens": 10000}
      }
    }
  ]
}
```

---

## 7. Digest Endpoint'leri

### GET /api/v1/digests _(Admin + Viewer)_

Bülten listesi. Kronolojik sıralama (en yeni önce).

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `cursor` | string | Hayır | Pagination cursor |
| `limit` | integer | Hayır | Sayfa boyutu (varsayılan: 10, max: 50) |
| `newsletter_slug` | string | Hayır | Bülten tipi (slug) filtresi |
| `status` | string | Hayır | Durum filtresi (varsayılan: `ready` — viewer yalnızca `ready` bültenleri görür) |

Viewer rolü yalnızca `status = ready` bültenleri görebilir. Admin tüm durumları görebilir.

**Response (200):**
```json
{
  "data": [
    {
      "id": "cc0e8400-...",
      "newsletter_slug": "fmcg_weekly",
      "title": "FMCG Haftalık Bülten — 9-15 Haziran 2026",
      "status": "ready",
      "period_start": "2026-06-09",
      "period_end": "2026-06-15",
      "total_sources_used": 28,
      "created_at": "2026-06-15T10:00:00Z",
      "completed_at": "2026-06-15T10:05:32Z"
    }
  ],
  "pagination": {
    "next_cursor": "dd0e8400-...",
    "has_more": true
  }
}
```

### GET /api/v1/digests/{digest_id} _(Admin + Viewer)_

Bülten detayı. Haftalık `summary` + section'ları dahil eder.

**Response (200):**
```json
{
  "id": "cc0e8400-...",
  "newsletter_slug": "fmcg_weekly",
  "title": "FMCG Haftalık Bülten — 9-15 Haziran 2026",
  "summary": "Bu hafta kakao fiyatlarındaki düşüş, AB ambalaj direktifi ve Mondelez yeniden yapılanması öne çıktı...",
  "status": "ready",
  "period_start": "2026-06-09",
  "period_end": "2026-06-15",
  "total_sources_used": 28,
  "created_at": "2026-06-15T10:00:00Z",
  "completed_at": "2026-06-15T10:05:32Z",
  "sections": [
    {
      "id": "ee0e8400-...",
      "section_order": 1,
      "section_title": "Yıldız ve Rakipleri",
      "ai_summary": "Bu hafta global gıda sektöründe...",
      "impact_note": "Yıldız Holding'in bisküvi kategorisinde...",
      "source_references": [
        {
          "processed_item_id": "ff0e8400-...",
          "url": "https://foodnavigator.com/article/123",
          "title": "Global snack trends shift toward..."
        }
      ]
    }
  ]
}
```

`summary` = haftalık **Bülten Özeti** (editör LLM); en tepede gösterilir. Viewer `status != ready` bültene erişirse 404 döner (403 değil).

### POST /api/v1/digests/generate _(Admin only)_

Manuel bülten üretimi tetikler (3-aşamalı editör pipeline). `period_*` verilmezse `newsletter_templates.date_range_days`'ten hesaplanır.

**Request:**
```json
{
  "newsletter_template_id": "aa0e8400-...",
  "period_start": "2026-06-09",
  "period_end": "2026-06-15"
}
```

**Response (202 Accepted):**
```json
{
  "id": "gg0e8400-...",
  "status": "generating",
  "message": "Bülten üretimi başlatıldı."
}
```

İşlem asenkron çalışır; sonuç `GET /api/v1/digests/{id}` ile sorgulanır.

### POST /api/v1/digests/news-impact _(Admin + Viewer)_

Haber çekmecesindeki "Yıldız'ı nasıl etkiler?" butonunun anlık analizi. Tek haber **global** prompt ile LLM'e gönderilir; sonuç **kalıcılaştırılmaz**. Rate-limit: 20 req/dk (kullanıcı bazlı, `Docs/07` §9).

**Request:**
```json
{ "processed_item_id": "ff0e8400-..." }
```

**Response (200):**
```json
{ "analysis": "Mondelez'in yeniden yapılanması Yıldız için fırsat: Türkiye tesisinin düşük maliyeti..." }
```

**Hata:** `processed_item` bulunamazsa 404; tüm LLM provider'lar başarısızsa 503 `AI_PROVIDERS_UNAVAILABLE`.

### GET /api/v1/briefs/today _(Admin + Viewer)_

Ana sayfa (S-HOME) "Günün Özeti" (Executive Brief) kartının veri kaynağı. Bugün için üretilmiş günlük özeti ve istatistik bandını döner. Brief, o günkü `ready` bültenlerden türetilir; ayrı bir kalıcı kaynak değildir (read-only türev).

**Query parametreleri:** Yok.

**Response (200) — özet hazır:**
```json
{
  "summary": "Bu hafta **3 yeni bülten** yayınlandı; **FMCG kategorisinde** fiyat baskısı öne çıkıyor. Yıldız Holding'i etkileyen **2 kritik gelişme** raporlandı.",
  "stats": {
    "source_count": 28,
    "new_digest_count": 3,
    "processed_news_count": 142,
    "yildiz_impact_count": 2
  },
  "generated_at": "2026-06-16T09:15:00Z"
}
```

- `summary`: 2-4 cümlelik düz metin. Vurgulanacak ifadeler `**...**` (Markdown bold) ile işaretlenir; frontend bunları altın renkte (`.hl`) render eder. `dangerouslySetInnerHTML` kullanılmaz — yalnızca `**...**` token'ları parse edilir.
- `stats`: 4 metrik (kaynak, yeni bülten, işlenen haber, Yıldız etkili gelişme sayısı). Tümü `integer ≥ 0`.
- `generated_at`: ISO 8601 UTC; özetin üretildiği an.

**Response (404) — özet henüz üretilmedi:**
```json
{
  "error": {
    "code": "BRIEF_NOT_READY",
    "message": "Günün özeti henüz hazırlanmadı.",
    "details": {}
  }
}
```

Frontend bu durumu "Günün özeti hazırlanıyor…" (pending) olarak gösterir. Hiç `ready` bülten bulunmuyorsa `summary` boş string döner ve frontend "veri yok" (empty) durumunu render eder.

---

## 8. AI Chatbot Endpoint'leri

### POST /api/v1/chat _(Admin + Viewer)_

Chatbot'a soru gönderir. RAG pipeline ile yanıt üretir.

**Request:**
```json
{
  "question": "Bu hafta FMCG sektöründe önemli gelişmeler neler?",
  "digest_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `question` | string (min 1) | ✅ | Kullanıcı sorusu |
| `digest_id` | UUID | ❌ | Opsiyonel digest bağlamı (`S-DIGEST-DETAIL` FAB → `?digest_id=`). Gönderilirse RAG bağlamı bu bültene öncelik verir; verilmezse tüm içerik üzerinden yanıt üretilir. BE `AskRequest` bu alanı kabul etmiyorsa FE soru-yalnız fallback'e döner (422 probe). |

**Response (200):**
```json
{
  "answer": "Bu hafta FMCG sektöründe dikkat çeken gelişmeler...",
  "sources": [
    {
      "chunk_id": "hh0e8400-...",
      "processed_item_id": "ff0e8400-...",
      "title": "Global snack trends shift toward...",
      "url": "https://foodnavigator.com/article/123",
      "score": 0.91
    },
    {
      "chunk_id": "ii0e8400-...",
      "processed_item_id": "jj0e8400-...",
      "title": "Perakende sektöründe yeni trendler",
      "url": "https://perakende.org/haber/456",
      "score": 0.85
    }
  ],
  "model": "groq/llama-3.1-70b",
  "tokens_used": 2340
}
```

Her soru/yanıt çifti `chat_history` tablosuna otomatik yazılır.

### GET /api/v1/chat/history _(Admin only)_

Chatbot sohbet geçmişi. Admin tüm kullanıcıların geçmişini görür.

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `cursor` | string | Hayır | Pagination cursor |
| `limit` | integer | Hayır | Sayfa boyutu (varsayılan: 20, max: 50) |
| `user_id` | string | Hayır | Kullanıcı filtresi |
| `start_date` | date | Hayır | Başlangıç tarihi |
| `end_date` | date | Hayır | Bitiş tarihi |

**Response (200):**
```json
{
  "data": [
    {
      "id": "kk0e8400-...",
      "user_id": "550e8400-...",
      "user_name": "Ali Yılmaz",
      "question": "Bu hafta FMCG sektöründe...",
      "answer": "Bu hafta FMCG sektöründe...",
      "sources": [...],
      "tokens_used": 2340,
      "model": "groq/llama-3.1-70b",
      "created_at": "2026-06-16T08:30:00Z"
    }
  ],
  "pagination": {
    "next_cursor": "ll0e8400-...",
    "has_more": true
  }
}
```

Viewer kullanıcılar bu endpoint'e erişemez (403).

---

## 9. Bildirim Yönetimi Endpoint'leri

### GET /api/v1/notifications/preferences _(Admin only)_

Tüm kullanıcıların bildirim tercihlerini listeler.

**Response (200):**
```json
{
  "data": [
    {
      "user_id": "550e8400-...",
      "user_name": "Ali Yılmaz",
      "email_enabled": true,
      "push_enabled": true,
      "has_fcm_token": true
    }
  ]
}
```

`fcm_token` değeri güvenlik nedeniyle response'ta dönmez; yalnızca token olup olmadığı (`has_fcm_token`) gösterilir.

### PUT /api/v1/notifications/preferences/{user_id} _(Admin only)_

Kullanıcının bildirim tercihlerini günceller.

**Request:**
```json
{
  "email_enabled": true,
  "push_enabled": false
}
```

### POST /api/v1/notifications/fcm-token _(Admin + Viewer)_

Mobil uygulama FCM device token'ını kaydeder veya günceller. Uygulama her açılışta bu endpoint'i çağırır.

**Request:**
```json
{
  "fcm_token": "dGVzdC10b2tlbi..."
}
```

**Response (200):**
```json
{
  "message": "FCM token güncellendi."
}
```

### GET /api/v1/notifications/recipients _(Admin only)_

Digest ve hata bildirimi mail alıcılarını listeler (S-ADMIN-NOTIFICATIONS Bölüm 1).

**Response (200):**
```json
{
  "data": [
    {
      "id": "rr0e8400-...",
      "user_id": "550e8400-...",
      "user_name": "Ali Yılmaz",
      "email": "ali@yildizholding.com",
      "types": ["digest", "error_alert"]
    }
  ]
}
```

`types` değerleri: `digest` (digest gönderimi), `error_alert` (toplama/işleme hata bildirimi).

### POST /api/v1/notifications/recipients _(Admin only)_

Mevcut bir kullanıcıyı mail alıcı listesine ekler. Aynı kullanıcı birden fazla kez eklenemez (409 `RECIPIENT_EXISTS`).

**Request:**
```json
{
  "user_id": "550e8400-...",
  "types": ["digest"]
}
```

**Response (201):** Eklenen alıcı kaydı (`NotificationRecipientItem` şeması — yukarıdaki liste öğesiyle aynı).

### DELETE /api/v1/notifications/recipients/{id} _(Admin only)_

Alıcıyı listeden kaldırır.

**Response (204):** Body yok.

---

## 10. Audit Log Endpoint'leri

### GET /api/v1/audit-logs _(Admin only)_

Sistem olaylarını listeler.

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `cursor` | string | Hayır | Pagination cursor |
| `limit` | integer | Hayır | Sayfa boyutu (varsayılan: 20, max: 100) |
| `event_type` | string | Hayır | Olay tipi filtresi |
| `actor_user_id` | string | Hayır | Aktör kullanıcı filtresi |
| `target_type` | string | Hayır | Hedef entity tipi filtresi |
| `start_date` | date | Hayır | Başlangıç tarihi |
| `end_date` | date | Hayır | Bitiş tarihi |

**Response (200):**
```json
{
  "data": [
    {
      "id": "mm0e8400-...",
      "event_type": "user.created",
      "actor_user_id": "550e8400-...",
      "actor_name": "Admin Kullanıcı",
      "target_type": "user",
      "target_id": "770e8400-...",
      "payload": {
        "email": "yeni@yildizholding.com",
        "role": "viewer"
      },
      "created_at": "2026-06-16T10:00:00Z"
    }
  ],
  "pagination": {
    "next_cursor": "nn0e8400-...",
    "has_more": true
  }
}
```

---

## 11. Sistem Ayarları Endpoint'leri

### GET /api/v1/settings _(Admin only)_

Tüm sistem ayarlarını döner.

**Response (200):**
```json
{
  "data": [
    {
      "key": "jwt_access_token_minutes",
      "value": 60,
      "description": "Access token geçerlilik süresi (dk)",
      "updated_at": "2026-06-01T10:00:00Z"
    },
    {
      "key": "jwt_refresh_token_days",
      "value": 30,
      "description": "Refresh token geçerlilik süresi (gün)",
      "updated_at": "2026-06-01T10:00:00Z"
    },
    {
      "key": "embedding_model",
      "value": "openai/text-embedding-3-small",
      "description": "Aktif embedding modeli",
      "updated_at": "2026-06-01T10:00:00Z"
    },
    {
      "key": "chatbot_rate_limit_per_minute",
      "value": 20,
      "description": "Chatbot dakika başına istek limiti (Min: 1, Max: 120)",
      "updated_at": "2026-06-01T10:00:00Z"
    },
    {
      "key": "chatbot_temperature",
      "value": 0.7,
      "description": "Chatbot yanıt sıcaklığı (Min: 0, Max: 2)",
      "updated_at": "2026-06-01T10:00:00Z"
    },
    {
      "key": "notification_schedule",
      "value": {
        "strategy_weekly": { "day": "friday", "time": "18:00", "enabled": true },
        "turkish_media_weekly": { "day": "saturday", "time": "10:00", "enabled": true },
        "fmcg_weekly": { "day": "saturday", "time": "12:00", "enabled": true },
        "daily_brief": { "day": "everyday", "time": "09:00", "enabled": true }
      },
      "description": "Digest tipi bazlı gönderim zamanlaması (S-ADMIN-NOTIFICATIONS Bölüm 2)",
      "updated_at": "2026-06-01T10:00:00Z"
    }
  ]
}
```

Ayar `value` alanı polimorfiktir: skaler (`jwt_*`, `chatbot_*`) veya nesne (`notification_schedule`) olabilir. `notification_schedule` öğelerinde `day` değerleri: `monday`–`sunday` veya `everyday`; `time` `HH:mm` formatında.

### PUT /api/v1/settings/{key} _(Admin only)_

Tek bir sistem ayarını günceller.

**Request:**
```json
{
  "value": 120
}
```

**Response (200):**
```json
{
  "key": "jwt_access_token_minutes",
  "value": 120,
  "description": "Access token geçerlilik süresi (dk)",
  "updated_at": "2026-06-16T11:00:00Z"
}
```

`embedding_model` değiştirildiğinde response'ta ek uyarı döner:

```json
{
  "key": "embedding_model",
  "value": "cohere/embed-v3",
  "warning": "Embedding modeli değişti. Reindex job arka planda başlatıldı.",
  "updated_at": "2026-06-16T11:00:00Z"
}
```

---

## 11.5 Pipeline Monitoring Endpoint'leri (Faz 6.1)

Admin'in pipeline çalıştırmalarını manuel tetikleyip izlediği kokpit endpoint'leri (S-ADMIN-PIPELINE). Tetikleme asenkrondur; ilerleme `GET /pipeline/runs/{id}` polling ile izlenir. Tüm endpoint'ler **Admin only**.

### POST /api/v1/pipeline/runs _(Admin only)_

Yeni bir pipeline çalıştırması tetikler. `collect_pipeline` collect→ingest→process→digest aşamalarını seçili kaynak tipleriyle koşar; `digest_update` yalnızca digest üretir.

**Request (collect_pipeline):**
```json
{
  "run_type": "collect_pipeline",
  "source_types": ["rss", "gov"]
}
```

**Request (digest_update):**
```json
{
  "run_type": "digest_update",
  "digest_type": "fmcg_weekly",
  "period_start": "2026-06-09",
  "period_end": "2026-06-15",
  "send_notification": true
}
```

**Alan kuralları:**
- `source_types`: yalnızca `collect_pipeline` için; izinli değerler `rss` | `email` | `gov` | `all`. `["all"]` → tüm aktif kaynak tipleri. `digest_update` için gönderilmez/yok sayılır.
- `digest_type`, `period_start`, `period_end`, `send_notification`: yalnızca `digest_update` için (kurallar `Docs/03` §7 `/digests/generate` ile aynı).

**Response (202 Accepted):**
```json
{
  "id": "pp0e8400-...",
  "run_type": "collect_pipeline",
  "status": "pending",
  "message": "Pipeline çalıştırması başlatıldı."
}
```

Aynı tipte `pending`/`running` bir run varken yeni `collect_pipeline` tetiklenirse `409 PIPELINE_ALREADY_RUNNING` döner (eşzamanlılık guard). Geçersiz `source_types` değeri `422 INVALID_SOURCE_TYPE`.

### GET /api/v1/pipeline/runs _(Admin only)_

Pipeline çalıştırma geçmişini listeler (cursor pagination).

**Query parametreleri:** `cursor`, `limit` (varsayılan 20, max 50), `run_type`, `status`, `start_date`, `end_date`.

**Response (200):**
```json
{
  "data": [
    {
      "id": "pp0e8400-...",
      "run_type": "collect_pipeline",
      "status": "running",
      "source_types": ["rss", "gov"],
      "stats": { "collected": 84, "ingested": 84, "processed": 51 },
      "triggered_by_name": "Admin Kullanıcı",
      "current_stage": "process",
      "started_at": "2026-06-20T08:00:00Z",
      "finished_at": null,
      "created_at": "2026-06-20T08:00:00Z"
    }
  ],
  "pagination": { "next_cursor": "qq0e8400-...", "has_more": true }
}
```

`current_stage`: `running` durumdaki run için o an koşan aşama; terminal durumda `null`.

### GET /api/v1/pipeline/runs/{run_id} _(Admin only)_

Tek bir run'ın aşama bazlı detayı — FE bu endpoint'i run koşarken polling ile çağırır.

**Response (200):**
```json
{
  "id": "pp0e8400-...",
  "run_type": "collect_pipeline",
  "status": "partial",
  "source_types": ["rss", "email", "gov"],
  "params": {},
  "stats": { "collected": 84, "ingested": 84, "processed": 51, "digest_id": "gg0e..." },
  "error_summary": "email kaynağı: IMAP bağlantı hatası",
  "triggered_by_name": "Admin Kullanıcı",
  "started_at": "2026-06-20T08:00:00Z",
  "finished_at": "2026-06-20T08:06:30Z",
  "created_at": "2026-06-20T08:00:00Z",
  "steps": [
    {
      "stage": "collect",
      "status": "completed",
      "sequence": 1,
      "items_in": 3,
      "items_out": 84,
      "items_failed": 1,
      "detail": { "rss": { "ok": 60 }, "gov": { "ok": 24 }, "email": { "failed": 1 } },
      "error_message": null,
      "started_at": "2026-06-20T08:00:05Z",
      "finished_at": "2026-06-20T08:02:00Z"
    },
    {
      "stage": "process",
      "status": "completed",
      "sequence": 3,
      "items_in": 84,
      "items_out": 51,
      "items_failed": 0,
      "detail": { "drain_polls": 7 },
      "error_message": null,
      "started_at": "2026-06-20T08:02:10Z",
      "finished_at": "2026-06-20T08:05:40Z"
    }
  ]
}
```

`steps` dizisi `sequence` sırasında döner (collect=1 … digest=4). `digest_update` run'ında koşmayan aşamalar `status: "skipped"`. Bulunmayan `run_id` → `404 PIPELINE_RUN_NOT_FOUND`.

### POST /api/v1/pipeline/runs/{run_id}/cancel _(Admin only)_

Koşan veya bekleyen bir run'ı iptal eder. Yalnızca `pending`/`running` iptal edilebilir; aksi halde `409 PIPELINE_NOT_CANCELLABLE`.

**Response (200):**
```json
{ "id": "pp0e8400-...", "status": "cancelled" }
```

---

## 11.6 İçerik Arşivi Endpoint'leri (Faz 6.2)

Admin'in processor çıktısını (`processed_items`) listeleyip filtrelediği arşiv endpoint'leri (S-ADMIN-CONTENT-ARCHIVE). **Admin only.** Viewer → `403 FORBIDDEN`.

### GET /api/v1/admin/processed-items _(Admin only)_

İşlenmiş haber içeriklerini listeler (cursor pagination). Yanıtta **`clean_content` dönmez** — tam metin için detay endpoint.

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `cursor` | string | Hayır | Önceki sayfa `next_cursor` (`{schema}:{uuid}` formatı) |
| `limit` | integer | Hayır | Varsayılan 20, max 100 |
| `source_id` | uuid | Hayır | Kaynak filtresi |
| `schema_category` | string | Hayır | Varsayılan davranış: yalnızca `news` (MVP-0 haber arşivi). `market`/`geo`/`fmcg`/`transport` MVP-0'da boş — filtre geçersiz değer `422` |
| `content_category` | string | Hayır | `macro` \| `fmcg` \| `finance` \| `geopolitical` \| `strategy` \| `regulatory` |
| `published_from` | date | Hayır | `published_at` alt sınır (dahil) |
| `published_to` | date | Hayır | `published_at` üst sınır (dahil) |
| `min_score` | float | Hayır | Min `relevance_score` (0–1) |
| `topic` | string | Hayır | `topics` JSONB contains (tek keyword) |
| `q` | string | Hayır | Başlık arama (case-insensitive ILIKE, min 2 karakter) |
| `has_digest` | boolean | Hayır | `true`: en az bir bülten referansı olan; `false`: hiç kullanılmamış |

**Response (200):**
```json
{
  "data": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440001",
      "schema_category": "news",
      "content_category": "macro",
      "source_id": "bb0e8400-e29b-41d4-a716-446655440002",
      "source_name": "Bloomberg HT RSS",
      "title": "TCMB faiz kararı piyasaları hareketlendirdi",
      "language": "tr",
      "relevance_score": 0.82,
      "topics": ["tcmb", "faiz", "enflasyon"],
      "published_at": "2026-06-18T09:30:00Z",
      "processed_at": "2026-06-18T09:31:12Z",
      "digest_usages": [
        {
          "digest_id": "cc0e8400-e29b-41d4-a716-446655440003",
          "digest_type": "strategy_weekly",
          "digest_title": "Strateji Haftalık — 9–15 Haziran 2026",
          "period_start": "2026-06-09",
          "period_end": "2026-06-15"
        }
      ]
    }
  ],
  "pagination": {
    "next_cursor": "news:dd0e8400-e29b-41d4-a716-446655440004",
    "has_more": true
  }
}
```

Geçersiz `schema_category` / `content_category` → `422 VALIDATION_ERROR`. `q` 1 karakter → `422 VALIDATION_ERROR`.

### GET /api/v1/admin/processed-items/{processed_item_id} _(Admin only)_

Tek işlenmiş içeriğin detayı. **`schema_category` query** varsayılan `news` (Faz 6.4); MVP-0'da tüm haberler `news.processed_items`'dadır.

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `schema_category` | string | Hayır | Varsayılan `news` |

**Response (200):**
```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440001",
  "schema_category": "news",
  "content_category": "macro",
  "source_id": "bb0e8400-e29b-41d4-a716-446655440002",
  "source_name": "Bloomberg HT RSS",
  "title": "TCMB faiz kararı piyasaları hareketlendirdi",
  "clean_content": "… tam normalize edilmiş metin …",
  "language": "tr",
  "relevance_score": 0.82,
  "topics": ["tcmb", "faiz", "enflasyon"],
  "entities": [],
  "published_at": "2026-06-18T09:30:00Z",
  "processed_at": "2026-06-18T09:31:12Z",
  "chunk_count": 3,
  "digest_usages": [
    {
      "digest_id": "cc0e8400-e29b-41d4-a716-446655440003",
      "digest_type": "strategy_weekly",
      "digest_title": "Strateji Haftalık — 9–15 Haziran 2026",
      "period_start": "2026-06-09",
      "period_end": "2026-06-15",
      "section_title": "Makroekonomik Gelişmeler"
    }
  ]
}
```

Bulunamaz → `404 PROCESSED_ITEM_NOT_FOUND`.

---

## 11.7 Keyword Takibi Endpoint'leri (Faz 6.3)

Admin'in kategori-bazlı keyword havuzunu (tr/en + 1–10 rating, çok-kategorili) yönettiği endpoint'ler (S-ADMIN-KEYWORDS). **Admin only.** Viewer → `403 FORBIDDEN`. Her yazma işlemi audit log üretir (`Docs/07` §9).

### GET /api/v1/admin/keywords _(Admin only)_

Keyword havuzunu listeler (offset pagination — havuz küçük, cursor gerekmez).

**Query parametreleri:**

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `category` | string | Hayır | Tek kategoriye göre filtre (`macro`\|`finance`\|`fmcg`\|`strategy`\|`geopolitical`\|`regulatory`) |
| `q` | string | Hayır | `term_tr`/`term_en` ILIKE arama (min 2 karakter) |
| `is_active` | boolean | Hayır | Aktiflik filtresi |
| `page` | integer | Hayır | Varsayılan 1 |
| `page_size` | integer | Hayır | Varsayılan 50, max 200 |

**Response (200):**
```json
{
  "data": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440010",
      "term_tr": "enflasyon",
      "term_en": "inflation",
      "is_active": true,
      "categories": [
        { "category": "macro", "rating": 9 },
        { "category": "finance", "rating": 6 }
      ],
      "created_at": "2026-06-20T08:00:00Z",
      "updated_at": "2026-06-20T08:00:00Z"
    }
  ],
  "pagination": { "page": 1, "page_size": 50, "total": 142 }
}
```

### POST /api/v1/admin/keywords _(Admin only)_

Yeni keyword + kategori rating'leri oluşturur.

**Request:**
```json
{
  "term_tr": "tedarik zinciri",
  "term_en": "supply chain",
  "is_active": true,
  "categories": [
    { "category": "fmcg", "rating": 7 },
    { "category": "strategy", "rating": 5 }
  ]
}
```

**Kurallar:**
- `term_tr`, `term_en`: zorunlu, 1–120 karakter, trim sonrası boş olamaz.
- `categories`: en az 1 öğe; her `rating` 1–10 tamsayı; aynı `category` iki kez verilemez → `422 VALIDATION_ERROR`.
- `term_tr` veya `term_en` (case-insensitive) zaten varsa → `409 KEYWORD_DUPLICATE`.

**Response (201):** Oluşan keyword (GET ile aynı şema).

### PUT /api/v1/admin/keywords/{keyword_id} _(Admin only)_

Keyword'ü ve kategori rating setini günceller. `categories` **tam set** olarak gönderilir (eksik kategoriler silinir, yeni olanlar eklenir, var olanların rating'i güncellenir — upsert/replace semantiği).

**Request:** POST ile aynı gövde (kısmi alanlar opsiyonel; `categories` verilirse tam set).

**Response (200):** Güncel keyword. Bulunamaz → `404 KEYWORD_NOT_FOUND`. Duplicate term → `409 KEYWORD_DUPLICATE`.

### DELETE /api/v1/admin/keywords/{keyword_id} _(Admin only)_

Keyword'ü ve bağlı rating'lerini siler (CASCADE). Bulunamaz → `404 KEYWORD_NOT_FOUND`. **Response (204).**

> **Not:** Kalıcı silme yerine pasifleştirme için `PUT … {"is_active": false}` tercih edilir; processor yalnızca aktif keyword'leri yükler. Silme audit log'da `keyword.deleted` olarak kaydedilir.

---

## 12. Yetki Matrisi

Tüm endpoint'lerin rol bazlı erişim tablosu. ✅ = erişim var, ❌ = erişim yok (403).

| Endpoint | Method | Admin | Viewer | Auth Gerekli |
|----------|--------|-------|--------|-------------|
| `/auth/login` | POST | ✅ | ✅ | Hayır |
| `/auth/refresh` | POST | ✅ | ✅ | Hayır |
| `/auth/logout` | POST | ✅ | ✅ | Evet |
| `/auth/password-reset/initiate` | POST | ✅ | ❌ | Evet |
| `/auth/password-reset/complete` | POST | ✅ | ✅ | Hayır |
| `/users` | GET | ✅ | ❌ | Evet |
| `/users` | POST | ✅ | ❌ | Evet |
| `/users/{id}` | GET | ✅ | ❌ | Evet |
| `/users/{id}` | PUT | ✅ | ❌ | Evet |
| `/users/me` | GET | ✅ | ✅ | Evet |
| `/sources` | GET | ✅ | ❌ | Evet |
| `/sources` | POST | ✅ | ❌ | Evet |
| `/sources/{id}` | PUT | ✅ | ❌ | Evet |
| `/sources/{id}` | DELETE | ✅ | ❌ | Evet |
| `/sources/{id}/status` | PATCH | ✅ | ❌ | Evet |
| `/newsletter-templates` | GET | ✅ | ❌ | Evet |
| `/newsletter-templates` | POST | ✅ | ❌ | Evet |
| `/newsletter-templates/{id}` | GET | ✅ | ❌ | Evet |
| `/newsletter-templates/{id}` | PUT | ✅ | ❌ | Evet |
| `/newsletter-templates/{id}` | DELETE | ✅ | ❌ | Evet |
| `/api-keys` | GET | ✅ | ❌ | Evet |
| `/api-keys` | POST | ✅ | ❌ | Evet |
| `/api-keys/{id}` | DELETE | ✅ | ❌ | Evet |
| `/api-keys/{id}/status` | PATCH | ✅ | ❌ | Evet |
| `/api-keys/usage-stats` | GET | ✅ | ❌ | Evet |
| `/digests` | GET | ✅ | ✅ | Evet |
| `/digests/{id}` | GET | ✅ | ✅ | Evet |
| `/digests/generate` | POST | ✅ | ❌ | Evet |
| `/digests/news-impact` | POST | ✅ | ✅ | Evet |
| `/chat` | POST | ✅ | ✅ | Evet |
| `/chat/history` | GET | ✅ | ❌ | Evet |
| `/notifications/preferences` | GET | ✅ | ❌ | Evet |
| `/notifications/preferences/{uid}` | PUT | ✅ | ❌ | Evet |
| `/notifications/fcm-token` | POST | ✅ | ✅ | Evet |
| `/notifications/recipients` | GET | ✅ | ❌ | Evet |
| `/notifications/recipients` | POST | ✅ | ❌ | Evet |
| `/notifications/recipients/{id}` | DELETE | ✅ | ❌ | Evet |
| `/audit-logs` | GET | ✅ | ❌ | Evet |
| `/settings` | GET | ✅ | ❌ | Evet |
| `/settings/{key}` | PUT | ✅ | ❌ | Evet |
| `/pipeline/runs` | POST | ✅ | ❌ | Evet |
| `/pipeline/runs` | GET | ✅ | ❌ | Evet |
| `/pipeline/runs/{id}` | GET | ✅ | ❌ | Evet |
| `/pipeline/runs/{id}/cancel` | POST | ✅ | ❌ | Evet |
| `/admin/processed-items` | GET | ✅ | ❌ | Evet |
| `/admin/processed-items/{id}` | GET | ✅ | ❌ | Evet |
| `/admin/keywords` | GET | ✅ | ❌ | Evet |
| `/admin/keywords` | POST | ✅ | ❌ | Evet |
| `/admin/keywords/{id}` | PUT | ✅ | ❌ | Evet |
| `/admin/keywords/{id}` | DELETE | ✅ | ❌ | Evet |

Guard implementasyonu: FastAPI dependency injection ile `get_current_user` ve `require_admin` dependency'leri kullanılır. Her endpoint fonksiyonunda `Depends(require_admin)` veya `Depends(get_current_user)` belirtilir.

```python
# Referans pattern
from fastapi import Depends, HTTPException

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """JWT token'dan kullanıcı çözümler. 401 döner: geçersiz/expired token."""
    ...

async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Admin rolü kontrolü. 403 döner: viewer erişimi."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Bu işlem için yönetici yetkisi gereklidir."}})
    return user

# Endpoint kullanımı
@router.get("/users")
async def list_users(admin: User = Depends(require_admin)):
    ...

@router.get("/digests")
async def list_digests(user: User = Depends(get_current_user)):
    ...
```

---

## 13. Error Taxonomy

### Standart Error Response Formatı

Tüm API hataları aşağıdaki formatta döner:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "İnsan okunabilir Türkçe açıklama.",
    "details": {}
  }
}
```

- `code`: Uygulama hata kodu (UPPER_SNAKE_CASE). Frontend bu değere göre koşullu davranış uygular.
- `message`: Kullanıcıya gösterilebilir Türkçe mesaj.
- `details`: Opsiyonel ek bilgi (validation hataları, alan bazlı detay).

### HTTP Status Code Eşleştirmesi

| Status | Anlam | Kullanım |
|--------|-------|---------|
| 200 | OK | Başarılı okuma veya güncelleme |
| 201 | Created | Başarılı kayıt oluşturma |
| 202 | Accepted | Asenkron işlem başlatıldı (digest üretimi) |
| 400 | Bad Request | Validation hatası, geçersiz parametre |
| 401 | Unauthorized | Token yok, geçersiz veya süresi dolmuş |
| 403 | Forbidden | Yetki yetersiz (viewer → admin endpoint) |
| 404 | Not Found | Kaynak bulunamadı |
| 409 | Conflict | Çakışma (duplicate email, aynı content_hash) |
| 422 | Unprocessable Entity | Pydantic validation hatası (FastAPI varsayılanı) |
| 429 | Too Many Requests | Rate limit aşıldı |
| 500 | Internal Server Error | Beklenmeyen sunucu hatası |

### Uygulama Hata Kodları Kataloğu

**Auth hataları:**

| Kod | Status | Açıklama |
|-----|--------|----------|
| `AUTH_INVALID_CREDENTIALS` | 401 | E-posta veya şifre hatalı |
| `AUTH_TOKEN_EXPIRED` | 401 | Access token süresi dolmuş |
| `AUTH_TOKEN_INVALID` | 401 | Token formatı geçersiz veya imzası doğrulanamıyor |
| `AUTH_INVALID_REFRESH_TOKEN` | 401 | Refresh token geçersiz veya süresi dolmuş |
| `AUTH_INVALID_RESET_TOKEN` | 401 | Şifre sıfırlama token'ı geçersiz, kullanılmış veya süresi dolmuş |
| `AUTH_ACCOUNT_INACTIVE` | 403 | Kullanıcı hesabı pasif |
| `FORBIDDEN` | 403 | Yetersiz yetki (rol kontrolü) |

**Validation hataları:**

| Kod | Status | Açıklama |
|-----|--------|----------|
| `VALIDATION_ERROR` | 422 | Pydantic validation hatası |
| `PASSWORD_POLICY_VIOLATION` | 400 | Şifre politikasına uymayan (min 8, 1 büyük, 1 rakam) |
| `INVALID_PARAMETER` | 400 | Geçersiz query parametresi |

**Resource hataları:**

| Kod | Status | Açıklama |
|-----|--------|----------|
| `RESOURCE_NOT_FOUND` | 404 | İstenen kaynak bulunamadı |
| `BRIEF_NOT_READY` | 404 | Günün özeti (Executive Brief) henüz üretilmedi |
| `PIPELINE_RUN_NOT_FOUND` | 404 | İstenen pipeline çalıştırması bulunamadı |
| `PROCESSED_ITEM_NOT_FOUND` | 404 | İstenen işlenmiş içerik bulunamadı (İçerik Arşivi) |
| `KEYWORD_NOT_FOUND` | 404 | İstenen keyword bulunamadı (Keyword Takibi) |
| `KEYWORD_DUPLICATE` | 409 | `term_tr` veya `term_en` (case-insensitive) zaten kayıtlı |
| `USER_EMAIL_EXISTS` | 409 | E-posta adresi zaten kayıtlı |
| `SOURCE_DUPLICATE_URL` | 409 | Aynı URL'li kaynak zaten var |
| `PIPELINE_ALREADY_RUNNING` | 409 | Aynı tipte koşan/bekleyen bir pipeline çalıştırması var |
| `PIPELINE_NOT_CANCELLABLE` | 409 | Run terminal durumda — iptal edilemez |
| `INVALID_SOURCE_TYPE` | 422 | Geçersiz kaynak tipi (`rss`/`email`/`gov`/`all` dışı) |

**Rate limit hataları:**

| Kod | Status | Açıklama |
|-----|--------|----------|
| `RATE_LIMIT_EXCEEDED` | 429 | İstek limiti aşıldı |

**Sistem hataları:**

| Kod | Status | Açıklama |
|-----|--------|----------|
| `INTERNAL_ERROR` | 500 | Beklenmeyen sunucu hatası |
| `LLM_API_ERROR` | 500 | LLM API çağrısı başarısız (tüm key'ler tükenmiş) |
| `DIGEST_GENERATION_FAILED` | 500 | Bülten üretimi başarısız |

### Validation Hata Detay Formatı (422)

Pydantic validation hatalarında `details` alanı alan bazlı hataları içerir:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "İstek doğrulaması başarısız.",
    "details": {
      "fields": [
        {
          "field": "email",
          "message": "Geçerli bir e-posta adresi giriniz.",
          "type": "value_error"
        },
        {
          "field": "password",
          "message": "Şifre en az 8 karakter olmalıdır.",
          "type": "value_error"
        }
      ]
    }
  }
}
```

### Global Exception Handler

FastAPI'de global exception handler tanımlanır. Tüm yakalanmamış hatalar standart error formatına dönüştürülür:

```python
# Referans pattern
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Beklenmeyen bir hata oluştu.",
                "details": {}
            }
        }
    )
```

Production ortamında hata detayları (stack trace) response'ta dönmez; yalnızca `audit_logs`'a yazılır.

---

## 14. Pagination

Tüm liste endpoint'leri cursor-based pagination kullanır.

### Request Formatı

| Parametre | Tip | Zorunlu | Açıklama |
|-----------|-----|---------|----------|
| `cursor` | string | Hayır | Önceki response'taki `next_cursor` değeri. İlk sayfada gönderilmez. |
| `limit` | integer | Hayır | Sayfa boyutu. Endpoint'e göre varsayılan ve max değerler değişir. |

### Response Formatı

Her liste response'u `data` dizisi ve `pagination` objesi içerir:

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "550e8400-e29b-41d4-a716-446655440000",
    "has_more": true
  }
}
```

- `next_cursor`: Bir sonraki sayfanın başlangıç noktası. Son sayfada `null`.
- `has_more`: Daha fazla kayıt var mı.

### Sıralama

Cursor pagination `id` üzerinden çalışır. Varsayılan sıralama: `created_at DESC, id DESC`. Bu, en yeni kayıtların önce gelmesini ve aynı `created_at` değerine sahip kayıtların tutarlı sıralanmasını sağlar.

Digest listesi istisnası: `completed_at DESC, id DESC` sıralaması kullanılır (en son tamamlanan bülten önce).

### Endpoint Bazlı Limitler

| Endpoint | Varsayılan Limit | Max Limit |
|----------|-----------------|-----------|
| `/users` | 20 | 50 |
| `/sources` | 20 | 100 |
| `/digests` | 10 | 50 |
| `/chat/history` | 20 | 50 |
| `/audit-logs` | 20 | 100 |
| `/admin/processed-items` | 20 | 100 |

---

## 15. Rate Limiting

Redis sliding window counter ile uygulanır. Limit aşıldığında 429 döner.

### Limit Tanımları

| Kategori | Limit | Tanımlayıcı | Açıklama |
|----------|-------|-------------|----------|
| Genel API | 100 req/dk | Per user (JWT `sub` claim) | Tüm authenticated endpoint'ler |
| Auth (login) | 10 req/dk | Per IP | Brute-force koruması |
| Auth (refresh) | 20 req/dk | Per IP | Token refresh flood koruması |
| Chatbot | 20 req/dk | Per user | LLM API maliyetini kontrol altında tutma |
| Anlık Yıldız etki | 20 req/dk | Per user | `POST /digests/news-impact` — runtime LLM maliyetini sınırlama |
| Password reset | 3 req/saat | Per IP | Reset link flood koruması |
| Pipeline trigger | 5 req/dk | Per user | `POST /pipeline/runs` — maliyetli orkestrasyonu sınırlama (eşzamanlılık guard'a ek) |

### 429 Response Formatı

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "İstek limiti aşıldı. Lütfen bir süre bekleyin.",
    "details": {
      "retry_after_seconds": 42
    }
  }
}
```

`Retry-After` HTTP header'ı da eklenir.

### Redis Key Pattern

```
rate_limit:user:{user_id}:general        → 100/dk
rate_limit:ip:{client_ip}:auth_login     → 10/dk
rate_limit:ip:{client_ip}:auth_refresh   → 20/dk
rate_limit:user:{user_id}:chat           → 20/dk
rate_limit:ip:{client_ip}:password_reset → 3/saat
```

TTL: limit pencere süresine eşit (60s veya 3600s).

---

## 16. CORS Politikası

FastAPI middleware ile tanımlanır:

```python
# Referans pattern
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ygip.yildizholding.com",   # prod
        "http://localhost:3000",              # dev web
        "http://localhost:8081",              # dev mobile (Metro bundler)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=86400,
)
```

| Parametre | Prod | Dev |
|-----------|------|-----|
| `allow_origins` | `https://ygip.yildizholding.com` | `http://localhost:3000`, `http://localhost:8081` |
| `allow_credentials` | `true` | `true` |
| `allow_methods` | GET, POST, PUT, DELETE, PATCH | GET, POST, PUT, DELETE, PATCH |
| `max_age` | 86400 (24 saat) | 86400 |

Origin listesi ortam değişkeninden (`CORS_ALLOWED_ORIGINS`) okunur. Wildcard (`*`) kullanılmaz.

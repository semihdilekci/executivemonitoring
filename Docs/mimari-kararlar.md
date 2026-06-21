# YıldızHolding Global Intelligence Platform — Mimari Kararlar Dokümanı

> **Versiyon:** 0.2
> **Son güncelleme:** 2026-06-17
> **Durum:** İlk taslak — tüm MVP-0 kararları kapandı, 8 açık karar §18'de bekliyor.
> **Amaç:** Bu doküman `.md` ve `.mdc` dosyalarının tamamının referans alacağı tek doğruluk kaynağıdır. Tüm mimari ve iş kuralı kararları buraya işlenir.

---

## Terminoloji

| Türkçe | İngilizce (kod) | Açıklama |
|--------|-----------------|----------|
| Özet rapor / bülten | `digest` | AI tarafından üretilen haftalık/günlük rapor |
| Kaynak | `source` | RSS beslemesi, API veya e-posta newsletter kaynağı |
| İşleyici | `processor` | Dedup → normalize → gate → enrich → score pipeline worker |
| Toplayıcı | `collector` | Dış kaynaklardan veri çeken worker |
| Yönetici | `admin` | Sistem yönetimi rolü |
| Görüntüleyici | `viewer` | Salt-okuma kullanıcı rolü |
| Sohbet geçmişi | `chat_history` | Chatbot soru/yanıt kayıtları |

---

## İçindekiler

- [1. Proje Kimliği ve Kapsam](#1-proje-kimliği-ve-kapsam)
- [2. Kullanıcı Havuzu ve Ölçek](#2-kullanıcı-havuzu-ve-ölçek)
- [3. Kimlik Doğrulama ve Kullanıcı Yapısı](#3-kimlik-doğrulama-ve-kullanıcı-yapısı)
- [4. Yetkilendirme Mimarisi](#4-yetkilendirme-mimarisi)
- [5. Roller ve Yetki Yönetimi](#5-roller-ve-yetki-yönetimi)
- [6. Süreç (Workflow) Mimarisi](#6-süreç-workflow-mimarisi)
- [7. Görev Yönetimi](#7-görev-yönetimi)
- [8. Doküman Yönetimi](#8-doküman-yönetimi)
- [9. Admin Panelleri](#9-admin-panelleri)
- [10. Güvenlik ve KVKK](#10-güvenlik-ve-kvkk)
- [11. Denetim (Audit Log)](#11-denetim-audit-log)
- [12. Entegrasyonlar](#12-entegrasyonlar)
- [13. Bildirim Sistemi](#13-bildirim-sistemi)
- [14. Tech Stack](#14-tech-stack)
- [15. Altyapı ve Operasyon](#15-altyapı-ve-operasyon)
- [16. Test Stratejisi](#16-test-stratejisi)
- [17. Kod Organizasyonu ve Agent Kuralları](#17-kod-organizasyonu-ve-agent-kuralları)
- [18. Açık Kararlar — Tamamlanması Gerekenler](#18-açık-kararlar--tamamlanması-gerekenler)

---

## 1. Proje Kimliği ve Kapsam

**Karar [P-001]:** Proje adı `YıldızHolding Global Intelligence Platform`, kısa kodu `YGIP`'dir.

**Karar [P-002]:** Platform; makro, FMCG, finansal, jeopolitik ve stratejik verileri otomatik toplayıp AI ile özetleyen, üst yönetime haftalık/günlük rapor bülteni sunan, web ve mobil dashboard üzerinden erişilebilen kurumsal bir izleme platformudur.

**Karar [P-003]:** Platform tek kiracılı (single-tenant) dahili bir sistemdir; SaaS değildir, YıldızHolding'e özeldir.

**Karar [P-004]:** MVP-0 kapsamı — üç otomatik bülten: Türk Medyası Haftalık (Cumartesi), FMCG Haftalık (Cumartesi), Strateji Haftalık (Cuma). Web dashboard ve mobil uygulama MVP-0'dan itibaren aktiftir; mail, "yeni rapor hazır" bildirimi olarak çalışır, asıl içerik platformdadır.

**Karar [P-005]:** Faz planı dört aşamalıdır ve her faz öncekinin üzerine ekler, yeniden yazma yoktur:
- **MVP-0:** 3 bülten + web dashboard + mobil uygulama + AI chatbot (RSS/email kaynaklı)
- **MVP-1:** Piyasa verisi (Finnhub, FRED, emtia) + kural tabanlı alarm motoru + dashboard zenginleştirme
- **MVP-2:** Long-running collector'lar (AIS, USGS, ACLED) + RAG pipeline tam aktif + AI anomali tespiti + harita görünümü
- **MVP-3:** Ücretli FMCG veri kaynakları (Euromonitor, NIQ) + Oxford Economics + SAP/ERP iç entegrasyon

**Karar [P-006]:** Platform dili Türkçe'dir; tüm arayüz, mail içeriği ve AI çıktıları Türkçe üretilir.

**Karar [P-007]:** Platform YıldızHolding IT/bulut altyapısı (AWS kurumsal hesabı) üzerinde host edilir. [X-INF-001]

---

## 2. Kullanıcı Havuzu ve Ölçek

**Karar [S-001]:** Hedef kullanıcı kitlesi üst yönetimdir (CEO ofisi, CFO, strateji direktörleri). Operasyonel kullanıcı ve self-servis kayıt yoktur.

**Karar [S-002]:** MVP-0'da ~5-10 alıcı, tam platformda ~20-30 dahili kullanıcı öngörülmektedir.

**Karar [S-003]:** Peak eşzamanlı kullanıcı ~5-10 olarak tahmin edilmektedir. Belirleyici yük kullanıcı trafiği değil, veri toplama pipeline'ının işlem hacmidir. [X-INF-002]

**Karar [S-004]:** Veri toplama hacimleri: 35+ RSS kaynağı 15 dk aralıkla, 9 e-posta kanalı saatlik, piyasa API'leri 5 dk aralıkla, resmi duyuru kaynakları 30 dk aralıkla sorgulanır.

**Karar [S-005]:** Sistem Türkiye'de çalışır, küresel veri izlenir ancak kişisel veri işlenmez. KVKK kapsamı uygulanır, GDPR gerektiren bir senaryo bulunmamaktadır.

**Karar [S-006]:** Alarm ve dashboard için gecikme toleransı near-real-time'dır; 5-15 dakika gecikme kabul edilebilir. Saniye bazlı gerçek zamanlı WebSocket akışı MVP-2'ye ertelenmiştir. [X-INF-004]

---

## 3. Kimlik Doğrulama ve Kullanıcı Yapısı

**Karar [A-001]:** Kimlik doğrulama yöntemi email + şifre'dir. Self-servis kayıt yoktur; kullanıcılar yalnızca admin tarafından oluşturulur.

**Karar [A-002]:** Auth MVP-0'dan itibaren aktiftir; dashboard ilk versiyondan itibaren kimlik doğrulama gerektirir. [X-AUTH-001]

**Karar [A-003]:** Kullanıcı attribute'ları: `id`, `email`, `full_name`, `role` (`admin` | `viewer`), `is_active`, `created_at`, `last_login_at`. Kişisel veri minimumda tutulur. [X-S-005]

---

## 4. Yetkilendirme Mimarisi

**Karar [AUTH-001]:** RBAC (Role-Based Access Control) benimsenir. Yetki çözümlemesi runtime'da yapılır; her API isteğinde JWT'den rol okunur, guard katmanında kontrol edilir. [X-A-001]

**Karar [AUTH-002]:** Dashboard route'ları ve API endpoint'leri rol bazlı guard/middleware ile korunur. `admin` tüm endpoint'lere erişir; `viewer` yalnızca okuma endpoint'lerine erişir, yönetim endpoint'leri yasaktır.

**Karar [AUTH-003]:** JWT'den çözümlenen rol yeterliliği sağlar; ek cache mekanizması MVP-0'da gerekmez. Kullanıcı sayısı düşük olduğundan her istekte DB'ye gidilmeksizin token claim'i kullanılır.

---

## 5. Roller ve Yetki Yönetimi

**Karar [R-001]:** İki sistem rolü tanımlanır:
- `admin`: Kullanıcı oluşturma/silme, kaynak (source) yönetimi, prompt şablon düzenleme, API key yönetimi, bildirim alıcı listesi yönetimi, audit log görüntüleme, sistem ayarları.
- `viewer`: Dashboard okuma, rapor görüntüleme, chatbot kullanımı, kendi bildirim tercihlerini görme.

**Karar [R-002]:** Rol ataması yalnızca admin tarafından yapılır. Kullanıcı kendi rolünü değiştiremez.

---

## 6. Süreç (Workflow) Mimarisi

> ⚪ Bu bölüm proje sahibi talimatıyla kapsam dışı bırakıldı (gerekçe: platform bir workflow/görev ürünü değildir; veri pipeline orkestrasyonu §15 Altyapı'da ele alınmaktadır).

---

## 7. Görev Yönetimi

> ⚪ Bu bölüm proje sahibi talimatıyla kapsam dışı bırakıldı (gerekçe: görev atama/yönetim senaryosu bulunmamaktadır).

---

## 8. Doküman Yönetimi

> ⚪ Bu bölüm proje sahibi talimatıyla kapsam dışı bırakıldı (gerekçe: kullanıcı dosya yükleme/indirme senaryosu yoktur; üretilen HTML arşivi §15'te S3 kapsamında ele alınmaktadır).

---

## 9. Admin Panelleri

**Karar [AP-001]:** Admin paneli aşağıdaki sayfaları içerir; tüm sayfalar yalnızca `admin` rolüne görünür:
1. **Kullanıcı Yönetimi** — kullanıcı oluştur/düzenle/pasif yap, rol ata.
2. **Kaynak Yönetimi** — RSS URL'leri, API endpoint'leri, e-posta newsletter göndericileri ekle/çıkart/aktif-pasif yap.
3. **Prompt Şablon Yönetimi** — her bülten bölümü için AI prompt şablonlarını düzenle.
4. **API Yönetimi** — LLM API key'leri (Gemini, Groq) ekle/çıkart; token bazlı kullanım grafiği (günlük/haftalık/aylık, key bazında kırılım). [X-TS-005]
5. **Bildirim Yönetimi** — mail alıcı listesi, bildirim zamanlaması, JWT parametre ayarları. [X-SEC-002]
6. **Sohbet Geçmişi** — kullanıcı bazlı chatbot soru/yanıt kayıtları; kim, ne zaman, ne sordu, ne yanıt aldı. [X-AP-005]
7. **Audit Log** — sistem olayları, giriş/çıkış, kaynak değişikliği logları. [X-AUD-001]

**Karar [AP-002]:** Viewer dashboard'u aşağıdaki sayfaları içerir (üst **PillNav** navigasyonu; sol sidebar yok):
1. **Ana Sayfa** (`/`) — Günün özeti (Executive Brief) + okunmamış bülten teaser'ları.
2. **Bültenler** (`/digests`) — tüm bültenlerin listesi; tıklanınca detaya gidilir.
3. **Rapor Detay** (`/digests/[id]`) — bültenin tüm bölümleri, haber linkleri, AI özeti ve "Yıldız için" etki notları.
4. **AI Chatbot** (`/chatbot`) — serbest soru/yanıt arayüzü; MVP-0'da RSS + newsletter kaynaklı DB'den RAG ile yanıt üretir. [X-AP-003]

**Karar [AP-006]:** Admin kullanıcılar **sol sidebar** navigasyonu kullanır (Ana Menü + Yönetim bölümleri). Viewer kullanıcılar sidebar görmez; yalnızca PillNav ile üç viewer sayfasına erişir. İki navigasyon shell'i aynı oturumda birlikte render edilmez. Detay: `Docs/06_SCREEN_CATALOG.md` §Rol Bazlı Navigasyon.

**Karar [AP-003]:** AI Chatbot (RAG) MVP-0'dan itibaren aktiftir. Tüm DB verisi değil; soruya anlamsal olarak en yakın chunk'lar (`pgvector` similarity search) LLM'e context olarak verilir. Her yanıt kaynak referanslarıyla birlikte döner. [X-TS-005]

**Karar [AP-004]:** API Yönetimi sayfasında LLM API key'leri yönetilir. Token tükenmesi veya kota hatası durumunda sistem sıradaki aktif key'e geçer (round-robin fallback). Kullanım metrikleri `api_usage_logs` tablosunda saklanır; grafikler bu tablodan üretilir. [X-TS-005]

**Karar [AP-005]:** Chatbot sohbet geçmişi `chat_history` tablosunda saklanır: `id`, `user_id`, `question`, `answer`, `sources` (JSON — RAG kaynak referansları), `token_used`, `created_at`. Admin panelinde filtrelenebilir liste olarak görüntülenir. [X-AUD-001]

---

## 10. Güvenlik ve KVKK

**Karar [SEC-001]:** Hedef güvenlik seviyesi OWASP ASVS L1'dir. Kişisel veri işlenmediğinden KVKK kapsamı kullanıcı erişim logları ile sınırlıdır.

**Karar [SEC-002]:** Oturum yönetimi JWT access token + refresh token ile sağlanır. Access token süresi ve refresh token süresi admin paneli "Bildirim Yönetimi" sayfasından düzenlenebilir parametre olarak tutulur. Varsayılan: access token 60 dk, refresh token 30 gün. Mobil uygulama için aynı token altyapısı kullanılır. [X-A-001]

**Karar [SEC-003]:** API key ve secret yönetimi ortama göre ayrılır: development ortamında `.env` dosyası, production ortamında AWS Secrets Manager. Secret'lar kod repository'sine commit edilemez. [X-INF-001]

**Karar [SEC-004]:** Tüm API iletişimi HTTPS üzerinden yapılır. HTTP → HTTPS yönlendirmesi zorunludur.

**Karar [SEC-005]:** Şifre politikası — minimum 8 karakter, en az 1 büyük harf + 1 rakam. Şifreler bcrypt (min cost 12) ile hash'lenerek saklanır, plain-text hiçbir zaman loglanmaz.

**Karar [SEC-006]:** HTTP güvenlik başlıkları zorunludur: `HSTS`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy` (Next.js middleware'de tanımlanır).

**Karar [SEC-007]:** Input validation — tüm API endpoint'lerinde Pydantic (FastAPI) ile request body doğrulaması yapılır. SQL injection'a karşı ORM (SQLAlchemy) parametrik sorgu kullanılır, raw SQL yasaktır.

---

## 11. Denetim (Audit Log)

**Karar [AUD-001]:** Loglanacak olaylar: kullanıcı girişi/çıkışı, admin tarafından kullanıcı oluşturma/silme/rol değiştirme, kaynak (source) ekleme/silme, prompt şablon değiştirme, API key ekleme/silme, digest çalışma sonucu (başarı/hata), sistem hata olayları.

**Karar [AUD-002]:** Audit kayıtları `audit_logs` tablosunda tutulur. Şema: `id`, `event_type` (enum), `actor_user_id`, `target_type`, `target_id`, `payload` (JSONB), `created_at`. Retention: 90 gün aktif tabloda, sonra S3 arşivine taşınır.

**Karar [AUD-003]:** Audit log yalnızca `admin` rolüne görünür. Viewer erişimi yoktur.

---

## 12. Entegrasyonlar

**Karar [I-001]:** MVP-0 veri kaynağı tipleri üç kategoridedir:
- **RSS/Atom beslemeleri:** 35+ kaynak — Türk medyası (gazeteoksijen, dunya.com, bloomberght, perakende.org, fortuneturkey, tcmb.gov.tr), FMCG (foodnavigator-usa, foodnavigator, fooddive, bakeryandsnacks, confectionerynews, grocerydive, retaildive, foodmanufacture, dairyreporter), Strateji (hbr.org, mckinsey.com, sloanreview.mit.edu, technologyreview.com).
- **E-posta newsletter (Gmail IMAP):** 9 gönderici — Economist, Apollo, Morgan Stanley, BCG, eMarketer, Caixin, HBR Alert, NielsenIQ Brief, Baking Business.
- **Resmi kaynaklar RSS:** TCMB, KAP, Resmi Gazete.

**Karar [I-002]:** MVP-1 ile REST API kaynakları eklenir: Finnhub (hisse/kur), FRED (makro), FAO (gıda fiyat endeksi), Yahoo Finance (emtia vadeli fiyatlar).

**Karar [I-003]:** MVP-2 ile long-running WebSocket collector'lar eklenir: AISStream.io (gemi takibi), USGS (deprem), OpenSky (uçak). Bu collector'lar ECS Fargate üzerinde always-on servis olarak çalışır. [X-INF-002]

**Karar [I-004]:** MVP-2 ile periyodik API kaynakları eklenir: ACLED (çatışma olayları), GDELT BigQuery (medya izleme), GPSJam (GPS bozma haritası), NASA FIRMS (yangın tespiti).

**Karar [I-005]:** Bir veri kaynağına erişim başarısız olduğunda exponential backoff ile 3 retry yapılır. 3 deneme sonunda hata loglanır ve admin'e mail bildirimi gönderilir. Sistem diğer aktif kaynaklardan beslemeye devam eder, tek kaynak hatası digest üretimini durdurmaz. [X-AUD-001] [X-N-004]

---

## 13. Bildirim Sistemi

**Karar [N-001]:** Bildirim kanalları: e-posta (kurumsal SMTP) ve mobil push (Firebase Cloud Messaging — FCM, iOS + Android). Dev ortamında Gmail SMTP; production'da YıldızHolding kurumsal SMTP relay. [X-TS-007]

**Karar [N-002]:** Haftalık digest bildirimleri "yeni rapor hazır" tetikleyicisiyle gönderilir. İçerik teaser'dır; asıl içerik platforma yönlendirir. Zamanlama: Strateji → Cuma, Türk Medyası + FMCG → Cumartesi. [X-P-004]

**Karar [N-003]:** MVP-1'den itibaren alarm bildirimleri eklenir: kural tabanlı eşik aşımları (kur hareketi, TCMB kararı, emtia spike) anlık push + mail olarak iletilir. [X-I-002]

**Karar [N-004]:** Sistem hata bildirimleri (kaynak erişim hatası, digest üretim hatası) admin'e mail olarak gönderilir. [X-I-005]

**Karar [N-005]:** Bildirim tercihleri admin tarafından belirlenir; viewer kullanıcılar bildirim tercihlerini değiştiremez.

**Karar [N-006]:** Mobil push altyapısı Firebase Cloud Messaging (FCM) ile sağlanır; tek entegrasyon hem iOS hem Android'i kapsar. [X-TS-010]

---

## 13.5 Processor Pipeline — MVP-0 Enrichment ve Gate

**Karar [PROC-001]:** MVP-0'da processor enrichment **keyword/rules tabanlıdır**; LLM enrichment yok. LLM bütçesi digest + chatbot'a ayrılır. MVP-1'de `LLMEnricherProcessor` swap ile sentiment, entity extraction ve LLM ilgi skoru eklenir.

**Karar [PROC-002]:** Keyword matching yalnızca enrichment değil **gate** mekanizmasıdır. `sources.config.ingest_mode`: `"all"` (domain-specific kaynaklar, otomatik kabul) veya `"filtered"` (master keyword havuzunda ≥1 eşleşme zorunlu). Eşleşmeyen makaleler `processed_items` ve `content_chunks`'a yazılmaz. Gate normalize sonrası çalışır.

**Karar [PROC-003]:** `relevance_score` deterministik **saf keyword ilgisi** formülü: `0.7 * coverage + 0.3 * freq` — `coverage = min(eşleşen farklı keyword / 5, 1.0)`, `freq = min(ort geçiş / 3, 1.0)`. Source reliability weight kaldırıldı — tüm kaynaklar admin-curated. **Güncellik (freshness) skordan kaldırıldı** — bültenler tarih-pencereli seçildiğinden tüm adaylar aynı güncellik bandında; freshness konu-ilgisini bastırıyordu. Eski `eşleşen / master_havuz × freq` formülü keyword katkısını ~0.18'e ezdiğinden hiçbir haber %40'ı geçemiyordu. Eşleşme kelime-sınırı (`\b`) bazlı (substring değil). Kategori çözümleme: en çok keyword eşleşmesi → `default_category` tie-break → `ingest_mode: "all"` her zaman `default_category`.

Detay: `Docs/04_BACKEND_SPEC.md` §8.3–8.4; `Docs/10_IMPLEMENTATION_ROADMAP.md` Faz 3 §3.4–3.7.

---

## 14. Tech Stack

**Karar [TS-001]:** Backend dili Python'dur. Collector worker'lar, processor pipeline ve AI/RAG katmanı için ekosistem olgunluğu (feedparser, trafilatura, imaplib, SQLAlchemy, LangChain) nedeniyle tercih edilmiştir.

**Karar [TS-002]:** Birincil veritabanı PostgreSQL'dir. `pgvector` extension MVP-0 kurulumunda yüklenir (kullanılmasa da); schema bölümleme: `news`, `market`, `geo`, `transport`, `fmcg`. [X-INF-002]

**Karar [TS-003]:** Cache katmanı Redis'tir. MVP-0'da Upstash serverless ücretsiz tier yeterlidir; dedup hash seti, rate-limit sayaçları ve scheduler kilitleri için kullanılır.

**Karar [TS-004]:** Message queue AWS SQS Standard'dır. Topic-per-type pattern uygulanır; her kaynak tipi için ayrı queue, dead-letter queue zorunludur. [X-INF-001]

**Karar [TS-005]:** LLM API yönetimi — Groq ve Gemini API key'leri admin paneli "API Yönetimi" sayfasından eklenir/çıkartılır. Token tükenmesi veya kota hatası (`429`, `503`) alındığında sistem round-robin ile sıradaki aktif key'e geçer. API kullanım metrikleri `api_usage_logs` tablosunda saklanır. [X-AP-004]

**Karar [TS-006]:** Mail gönderim altyapısı kurumsal SMTP'dir (AWS SES kullanılmaz). Dev: Gmail SMTP + uygulama şifresi; prod: kurumsal relay. Kimlik bilgileri dev `.env`, prod Secrets Manager. [X-N-001]

**Karar [TS-007]:** Mobil push altyapısı Firebase Cloud Messaging (FCM)'dir. [X-N-006]

**Karar [TS-008]:** Cloud altyapısı AWS'dir (YıldızHolding IT). Servis tipleri: Lambda (short-lived collector'lar), ECS Fargate (long-running worker'lar MVP-2+), RDS PostgreSQL, ElastiCache/Upstash Redis, EventBridge (scheduler), S3 (arşiv). [X-INF-001]

**Karar [TS-009]:** Web frontend framework Next.js'tir. SSR desteği, API routes ve responsive tasarım için tercih edilmiştir. [X-AP-002]

**Karar [TS-010]:** Mobil uygulama framework React Native'dir. Next.js ile aynı ekosistem, tek codebase ile iOS + Android desteği sağlar. [X-N-006]

**Karar [TS-011]:** API katmanı FastAPI'dir (Python). Backend ile aynı dil, async destek ve otomatik OpenAPI/Swagger dokümantasyonu için tercih edilmiştir. Frontend (web + mobil) bu API üzerinden iletişim kurar.

**Karar [TS-012]:** ORM olarak SQLAlchemy kullanılır. Raw SQL yasaktır; tüm DB erişimi ORM parametrik sorguları üzerinden yapılır. [X-SEC-007]

**Karar [TS-013]:** RAG pipeline için pgvector similarity search kullanılır. Embedding üretimi için OpenAI text-embedding-3-small veya Cohere embed-v3 tercih edilir; model seçimi admin panelinden yapılandırılabilir.

---

## 15. Altyapı ve Operasyon

**Karar [INF-001]:** Cloud sağlayıcısı AWS'dir. YıldızHolding kurumsal AWS hesabı kullanılır. Secret yönetimi: dev `.env`, prod AWS Secrets Manager. [X-SEC-003] [X-P-007]

**Karar [INF-002]:** Servis mimarisi:
- **AWS Lambda:** RSS collector, email collector, REST API collector, gov collector (short-lived, EventBridge cron trigger).
- **ECS Fargate:** WebSocket collector'lar (AIS, USGS, OpenSky) — MVP-2'den itibaren, always-on.
- **RDS PostgreSQL:** t3.micro (MVP-0), t3.small (MVP-1+).
- **ElastiCache / Upstash Redis:** Dedup cache ve rate-limit sayaçları.
- **AWS SQS:** Topic-per-type message queue.
- **AWS EventBridge:** Cron scheduler.
- **AWS S3:** Ham içerik arşivi + üretilen digest HTML dosyaları.
- **SMTP (harici):** E-posta bildirimleri kurumsal SMTP relay üzerinden (IaC dışı). [X-TS-006]

**Karar [INF-003]:** Pipeline orkestrasyonu n8n kullanılmadan EventBridge → Lambda → SQS → Processor şeklinde kurulur. Her collector `BaseCollector` abstract class'ını implement eder; ana pipeline değişmeden yeni collector eklenebilir. [X-CODE-001]

**Karar [PIPE-002]:** SQS mesajından `raw_items` ingest, ayrı Lambda consumer yerine **Processor Lambda giriş adımında** idempotent yapılır (`ingest_message` reuse). Gerekçe: topic-per-type kuyrukta tek consumer; Faz 6.1 ingest/process gözlem aşamaları ile uyum. ADR: `docs/adr/0001-processor-ingest-at-entry.md`. [X-CODE-001]

**Karar [INF-004]:** Near-real-time tolerans 5-15 dakikadır. RSS 15 dk, piyasa API 5 dk, resmi duyurular 30 dk polling aralığıyla çalışır. [X-S-006]

**Karar [INF-005]:** İki ortam tanımlanır: `dev` ve `prod`. Ortam izolasyonu detayı açık karardır. [X-INF-OPEN-3]

**Karar [INF-006]:** CI/CD pipeline GitHub Actions ile yönetilir. AWS deploy action'ları GitHub Actions üzerinden çalışır. Her faz ayrı feature branch'te geliştirilir; `main` branch'e doğrudan push yapılamaz. [X-CODE-003]

**Karar [INF-007]:** MVP-0'da CloudWatch basic log yeterlidir. Detaylı monitoring (alarm eşikleri, Grafana kurulumu) MVP-1 için açık karardır. [X-INF-OPEN-2]

---

## 16. Test Stratejisi

**Karar [TEST-001]:** Test piramidi:
- **Unit test:** Collector veri çekimi, processor dedup/normalize/score mantığı, AI prompt çıktı formatı doğrulama. Hedef coverage: kritik iş mantığı %70+.
- **Integration test:** DB yazma/okuma, API mock ile collector davranışı, SQS mesaj akışı.
- **E2E test:** MVP-0'da kapsam dışı, MVP-1 dashboard ile değerlendirilir.

**Karar [TEST-002]:** Agent kuralı — **Claude Code / Cursor kullanıcı onayı olmadan `main` branch'e merge edemez.** PR açar, kod review + onay bekler.

**Karar [TEST-003]:** Seed stratejisi — dev ortamında gerçek RSS çekimi yerine `fixtures/` klasöründe JSON fixture dosyaları kullanılır. Production verisi dev ortamına taşınamaz.

---

## 17. Kod Organizasyonu ve Agent Kuralları

**Karar [CODE-001]:** Monorepo klasör yapısı:

```
/apps
  /api          → FastAPI backend (Python)
  /web          → Next.js web frontend
  /mobile       → React Native iOS + Android
/services
  /collectors   → RSS, email, API, gov, WebSocket worker'lar
  /processor    → dedup, normalize, gate, enrich, score pipeline
  /ai-engine    → digest üretici, RAG pipeline, alarm motoru, chatbot
/packages
  /shared       → ortak tipler, utils, DB schema (SQLAlchemy models)
/infra          → AWS CDK / Terraform
/fixtures       → dev ortamı test verisi
```

**Karar [CODE-002]:** Naming conventions:
- Klasör/dosya: `kebab-case`
- Class/Type (Python + TS): `PascalCase`
- Fonksiyon/değişken (Python): `snake_case` | (TypeScript): `camelCase`
- DB tablo/kolon: `snake_case`, tablo adları çoğul
- Env var / constant: `UPPER_SNAKE_CASE`
- React component dosyası: `PascalCase.tsx`

**Karar [CODE-003]:** Commit standardı Conventional Commits'tir: `feat:`, `fix:`, `chore:`, `refactor:`, `test:`, `docs:`. Branch adlandırma: `feature/mvp-0`, `feature/mvp-1`, `feature/mvp-2`, `feature/mvp-3`. Her faz ayrı feature branch'te geliştirilir; main'e merge ancak faz tamamlandığında ve onay alındıktan sonra yapılır. [X-INF-006]

**Karar [CODE-004]:** Agent yasak listesi — aşağıdaki aksiyonlar kullanıcı onayı olmadan yapılamaz:
1. `main` branch'e doğrudan push veya merge.
2. `.env` veya secrets dosyasına API key yazma.
3. DB migration'ı production ortamında onaysız çalıştırma.
4. `sources` tablosuna (collector kaynak listesi) onaysız kayıt ekleme/silme.
5. LLM prompt şablonunu onaysız production'a alma.
6. Herhangi bir AWS kaynak silme komutu çalıştırma.

**Karar [CODE-005]:** Her yeni feature'da kontrol listesi:
- [ ] Unit test yazıldı mı?
- [ ] Yeni env var varsa `.env.example`'a eklendi mi?
- [ ] Yeni DB tablosu varsa migration dosyası oluşturuldu mu?
- [ ] Yeni API endpoint varsa OpenAPI şeması güncellendi mi?
- [ ] Yeni collector varsa `BaseCollector` implement edildi mi?

---

## 18. Açık Kararlar — Tamamlanması Gerekenler

**Bu kararlar tamamlanmadan ilgili kod parçalarının geliştirilmesine başlanmamalıdır.**

| ID | Öncelik | Konu | Hedef Faz | Notlar |
|----|---------|------|-----------|--------|
| [I-OPEN-1] | 🔴 Kritik | Euromonitor Passport API erişim modeli ve entegrasyon sözleşmesi | MVP-3 öncesi | Satın alma + API dokümantasyonu bekleniyor |
| [I-OPEN-2] | 🔴 Kritik | NIQ Retail Measurement API erişim modeli | MVP-3 öncesi | Satın alma + API dokümantasyonu bekleniyor |
| [I-OPEN-3] | 🟠 Yüksek | Oxford Economics EPRE API entegrasyon detayları | MVP-3 öncesi | Fiyat müzakeresi tamamlanmadı |
| [I-OPEN-4] | 🟠 Yüksek | SAP/ERP iç entegrasyon bağlantı modeli (nightly sync mi, event-driven mi?) | MVP-3 öncesi | YH IT ile koordinasyon gerekli |
| [INF-OPEN-1] | 🟠 Yüksek | RDS backup/PITR stratejisi | MVP-1 öncesi | DevOps kararı — retention süresi, snapshot frekansı |
| [INF-OPEN-2] | 🟠 Yüksek | Monitoring detayı: CloudWatch alarm eşikleri, Grafana kurulum kararı | MVP-1 öncesi | DevOps kararı |
| [INF-OPEN-3] | 🟠 Yüksek | Dev/Prod ortam izolasyonu — ayrı AWS hesap mı, aynı hesapta prefix/namespace mi? | MVP-0 başlamadan | YH IT altyapı politikasına bağlı |
| [S-OPEN-1] | 🟢 Düşük | Eşzamanlı kullanıcı sayısı revizyonu | MVP-1 sonrası | Gerçek kullanım verisine göre gözden geçirilecek |

---

## Versiyon Geçmişi

| Versiyon | Tarih | Açıklama |
|----------|-------|----------|
| 0.1 | 2026-06-11 | İlk taslak. P-001..007, S-001..006, A-001..003, AUTH-001..003, R-001..002, AP-001..005, SEC-001..007, AUD-001..003, I-001..005, N-001..006, TS-001..013, INF-001..007, TEST-001..003, CODE-001..005 kararları alındı. §6, §7, §8 kapsam dışı bırakıldı. 8 açık karar §18'de bekliyor. |
| 0.2 | 2026-06-17 | AP-002 güncellendi; AP-006 eklendi — rol bazlı navigasyon (viewer: PillNav, admin: sidebar). `/digests` bülten listesi route'u. |

---

## Nasıl Kullanılır?

Bu doküman **canlı bir dokümandır** — kararlar netleştikçe güncellenecektir.

1. İlgili bölüme karar eklenir (`[KATEGORI-SIRA]` formatında ID verilir).
2. Karar açıksa §18'e `[KATEGORI-OPEN-N]` olarak öncelik etiketiyle yazılır; kapandığında listeden silinir ve versiyon geçmişine işlenir.
3. Bağlı kararlar `[X-ID]` cross-reference ile birbirine bağlanır.
4. Her session sonunda versiyon geçmişi güncellenir.

Bu doküman `project-doc-architect` skill'inin girdisidir — 11 bağımsız teknik doküman bu dosyadan üretilir.

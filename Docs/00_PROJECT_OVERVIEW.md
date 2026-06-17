# 00 — Proje Genel Bakış

## 1. Proje Kimliği

Proje adı **YıldızHolding Global Intelligence Platform**, kısa kodu **YGIP**'dir. Platform tek kiracılı (single-tenant) dahili bir kurumsal izleme sistemidir; SaaS değildir, yalnızca YıldızHolding bünyesinde kullanılır. Tüm arayüz, e-posta içeriği ve AI çıktıları Türkçe üretilir.

---

## 2. Amaç ve Hedef Kitle

YGIP; makro ekonomi, FMCG sektörü, finansal piyasalar, jeopolitik gelişmeler ve stratejik içerikleri otomatik olarak toplar, AI ile özetler ve üst yönetime haftalık/günlük rapor bültenleri sunar. Kullanıcılar web dashboard ve mobil uygulama üzerinden içeriğe erişir; e-posta yalnızca "yeni rapor hazır" bildirimi taşır, asıl içerik her zaman platformda okunur.

Hedef kullanıcı kitlesi üst yönetimdir: CEO ofisi, CFO, strateji direktörleri. Operasyonel kullanıcı ve self-servis kayıt bulunmaz. Tüm kullanıcılar admin tarafından oluşturulur.

Ölçek tahminleri:

| Metrik | MVP-0 | Tam Platform |
|--------|-------|-------------|
| Toplam kullanıcı | ~5-10 | ~20-30 |
| Peak eşzamanlı kullanıcı | ~5 | ~10 |
| Belirleyici yük kaynağı | Veri toplama pipeline | Veri toplama pipeline |

Sistem yükünü kullanıcı trafiği değil, veri toplama pipeline'ının işlem hacmi belirler.

---

## 3. Kapsam ve Sınırlar

### Platform ne yapar

- Dış kaynaklardan (RSS, e-posta newsletter, REST API, WebSocket, resmi duyurular) veri toplar.
- Toplanan veriyi dedup → normalize → enrich → score pipeline'ından geçirir.
- AI ile haftalık/günlük bültenler (digest) üretir ve kullanıcılara sunar.
- RAG tabanlı AI chatbot ile kullanıcıların toplanan veriye soru sormasını sağlar.
- Kural tabanlı alarmlarla kritik gelişmeleri anlık bildirir (MVP-1+).

### Platform ne yapmaz

- Workflow veya görev yönetimi içermez.
- Doküman yükleme/indirme senaryosu yoktur.
- Self-servis kullanıcı kaydı yoktur.
- Dış müşteriye açık bir SaaS servisi değildir.
- Saniye bazlı gerçek zamanlı veri akışı sağlamaz (near-real-time, 5-15 dk tolerans).

---

## 4. Faz Planı

Her faz öncekinin üzerine ekler; yeniden yazma yoktur.

| Faz | Kapsam | Eklenen Veri Kaynakları | Eklenen Yetenekler |
|-----|--------|------------------------|-------------------|
| **MVP-0** | 3 haftalık bülten + web dashboard + mobil uygulama + AI chatbot | 35+ RSS, 9 e-posta newsletter, resmi kaynaklar (TCMB, KAP, Resmi Gazete) | Auth, admin paneli, digest üretimi, RAG chatbot, push/e-posta bildirimi |
| **MVP-1** | Piyasa verisi + alarm motoru + dashboard zenginleştirme | Finnhub (hisse/kur), FRED (makro), FAO (gıda fiyat endeksi), Yahoo Finance (emtia) | Kural tabanlı alarm motoru, anlık push/mail bildirimi, CloudWatch detaylı monitoring, Grafana |
| **MVP-2** | Long-running collector'lar + RAG pipeline tam aktif + harita görünümü | AISStream.io (gemi), USGS (deprem), OpenSky (uçak), ACLED (çatışma), GDELT (medya), GPSJam (GPS bozma), NASA FIRMS (yangın) | WebSocket collector'lar (ECS Fargate always-on), AI anomali tespiti, harita görünümü |
| **MVP-3** | Ücretli FMCG kaynakları + iç entegrasyon | Euromonitor Passport, NIQ Retail Measurement, Oxford Economics EPRE | SAP/ERP nightly batch sync, ücretli API entegrasyonları |

MVP-0 bülten zamanlaması:

| Bülten | Gün | Tetikleyici |
|--------|-----|------------|
| Strateji Haftalık | Cuma | EventBridge cron |
| Türk Medyası Haftalık | Cumartesi | EventBridge cron |
| FMCG Haftalık | Cumartesi | EventBridge cron |

---

## 5. Tech Stack Özeti

| Katman | Teknoloji | Notlar |
|--------|----------|-------|
| Backend API | Python + FastAPI | Async destek, otomatik OpenAPI/Swagger |
| ORM | SQLAlchemy | Raw SQL yasak, parametrik sorgu zorunlu |
| Web Frontend | Next.js | SSR, responsive |
| Mobil | React Native | iOS + Android tek codebase, enterprise dağıtım |
| Veritabanı | PostgreSQL + pgvector | Schema bölümleme: `news`, `market`, `geo`, `transport`, `fmcg` |
| Cache | Redis (Upstash serverless) | Dedup hash, rate-limit sayaçları, scheduler kilitleri |
| Message Queue | AWS SQS Standard | Topic-per-type, dead-letter queue zorunlu |
| Scheduler | AWS EventBridge | Cron trigger'lar |
| Compute (short-lived) | AWS Lambda | Collector'lar (RSS, email, API, gov) |
| Compute (long-running) | ECS Fargate | WebSocket collector'lar (MVP-2+) |
| Object Storage | AWS S3 | Ham içerik arşivi, digest HTML snapshot |
| Secret Yönetimi | `.env` (dev), AWS Secrets Manager (prod) | Secret'lar repo'ya commit edilemez |
| LLM API | Groq + Gemini | Round-robin fallback, admin panelinden key yönetimi |
| Embedding | OpenAI text-embedding-3-small veya Cohere embed-v3 | Admin panelinden model seçimi |
| E-posta | AWS SES + SMTP | Bildirim ve sistem hata mailleri |
| Push Bildirim | Firebase Cloud Messaging (FCM) | iOS + Android tek entegrasyon |
| CI/CD | GitHub Actions | Feature branch per faz, main'e doğrudan push yasak |

---

## 6. Veri Kaynağı Haritası

### MVP-0 — RSS/Atom Beslemeleri (35+ kaynak)

| Kategori | Örnek Kaynaklar | Polling Aralığı |
|----------|----------------|----------------|
| Türk Medyası | gazeteoksijen, dunya.com, bloomberght, perakende.org, fortuneturkey, tcmb.gov.tr | 15 dk |
| FMCG Sektörü | foodnavigator-usa, foodnavigator, fooddive, bakeryandsnacks, confectionerynews, grocerydive, retaildive, foodmanufacture, dairyreporter | 15 dk |
| Strateji | hbr.org, mckinsey.com, sloanreview.mit.edu, technologyreview.com | 15 dk |
| Resmi Kaynaklar | TCMB, KAP, Resmi Gazete | 30 dk |

### MVP-0 — E-posta Newsletter (9 gönderici, Gmail IMAP)

Economist, Apollo, Morgan Stanley, BCG, eMarketer, Caixin, HBR Alert, NielsenIQ Brief, Baking Business. Saatlik polling.

### MVP-1 — REST API Kaynakları

Finnhub (hisse/kur), FRED (makro), FAO (gıda fiyat endeksi), Yahoo Finance (emtia). 5 dk polling.

### MVP-2 — WebSocket + Periyodik API

WebSocket (always-on): AISStream.io, USGS, OpenSky. Periyodik API: ACLED, GDELT BigQuery, GPSJam, NASA FIRMS.

### MVP-3 — Ücretli Kaynaklar + İç Entegrasyon

Euromonitor Passport API, NIQ Retail Measurement, Oxford Economics EPRE. SAP/ERP nightly batch sync.

---

## 7. Ortam ve Altyapı

Platform YıldızHolding kurumsal AWS hesabı üzerinde host edilir. İki ortam tanımlıdır:

| Ortam | Amaç | Kaynak Adlandırma | Secret Yönetimi |
|-------|------|-------------------|----------------|
| `dev` | Geliştirme ve test | `dev-` prefix (örn: `dev-ygip-rds`, `dev-ygip-sqs-rss`) | `.env` dosyası |
| `prod` | Canlı sistem | `prod-` prefix (örn: `prod-ygip-rds`, `prod-ygip-sqs-rss`) | AWS Secrets Manager |

Ortam izolasyonu aynı AWS hesapta `dev-` / `prod-` prefix ile namespace ayrımı ile sağlanır. RDS instance'ları ayrıdır; Lambda, SQS ve S3 kaynak adları prefix ile birbirinden izole edilir.

CI/CD pipeline GitHub Actions ile yönetilir. Her MVP fazı ayrı feature branch'te geliştirilir (`feature/mvp-0`, `feature/mvp-1` vb.). `main` branch'e doğrudan push yapılamaz; merge ancak faz tamamlandığında ve onay alındıktan sonra gerçekleşir.

---

## 8. Başarı Kriterleri

MVP-0 aşağıdaki koşullar sağlandığında tamamlanmış sayılır:

| # | Kriter | Doğrulama Yöntemi |
|---|--------|-------------------|
| 1 | 3 haftalık bülten (Strateji, Türk Medyası, FMCG) zamanında otomatik üretiliyor | EventBridge cron tetikleniyor, digest `digests` tablosuna yazılıyor, S3'e HTML arşivi oluşuyor |
| 2 | Web dashboard'dan bültenler okunabiliyor | Viewer: PillNav → Bültenler → detay; Admin: sidebar → aynı akış; her iki rolde login sonrası içerik erişilebilir |
| 3 | Mobil uygulama (iOS + Android) aynı içeriğe erişebiliyor | Enterprise dağıtım ile yüklenen uygulama login → rapor okuma akışını tamamlıyor |
| 4 | AI chatbot RSS + newsletter verisinden RAG ile yanıt üretiyor | Chatbot'a soru sorulduğunda pgvector similarity search çalışıyor, kaynak referanslı yanıt dönüyor |
| 5 | Auth aktif — kimlik doğrulama olmadan hiçbir sayfaya erişilemiyor | Login olmadan dashboard route'larına istek atıldığında 401 dönüyor |
| 6 | Admin paneli 7 sayfası çalışıyor | Kullanıcı yönetimi, kaynak yönetimi, prompt şablon, API yönetimi, bildirim, sohbet geçmişi, audit log sayfaları fonksiyonel |
| 7 | "Yeni rapor hazır" bildirimi e-posta ve push ile gönderiliyor | Digest üretimi tamamlandığında SES mail ve FCM push bildirimi alıcılara ulaşıyor |

---

## 9. Kısıtlar ve Riskler

### Teknik Kısıtlar

- **Near-real-time tolerans:** Alarm ve dashboard için 5-15 dakika gecikme kabul edilir. Saniye bazlı gerçek zamanlı WebSocket akışı MVP-2 kapsamındadır.
- **KVKK:** Kişisel veri işlenmez; KVKK kapsamı kullanıcı erişim logları ile sınırlıdır. GDPR gerektiren senaryo bulunmaz.
- **HTTPS zorunluluğu:** Tüm API iletişimi HTTPS üzerinden yapılır. HTTP → HTTPS yönlendirmesi zorunludur.
- **Raw SQL yasağı:** Tüm veritabanı erişimi SQLAlchemy ORM parametrik sorguları ile yapılır.

### Riskler

| Risk | Etki | Azaltma |
|------|------|---------|
| MVP-3 ücretli kaynak sözleşmeleri (Euromonitor, NIQ, Oxford Economics) henüz kapanmamıştır | MVP-3 başlangıcı gecikebilir | Collector abstract pattern hazır; sözleşme kapandığında spesifik implementasyon eklenir |
| SAP/ERP entegrasyon modeli YH IT koordinasyonu gerektirir | MVP-3 iç entegrasyon kapsamı değişebilir | Nightly batch sync varsayımı ile tasarım yapılır; event-driven geçiş opsiyoneldir |
| RDS backup stratejisi DevOps kararı olarak beklemektedir | MVP-1 öncesi kesinleştirilmelidir | Varsayılan: daily snapshot, 7 gün retention, PITR aktif |
| Monitoring eşikleri ve Grafana kurulumu MVP-1 öncesi planlanmalıdır | Canlı sistem görünürlüğü MVP-0'da sınırlıdır | MVP-0'da CloudWatch basic metrics + Lambda error alarm yeterlidir |

---

## 10. Terminoloji

| Türkçe | İngilizce (kod) | Açıklama |
|--------|-----------------|----------|
| Özet rapor / bülten | `digest` | AI tarafından üretilen haftalık/günlük rapor |
| Kaynak | `source` | RSS beslemesi, API veya e-posta newsletter kaynağı |
| İşleyici | `processor` | Dedup → normalize → enrich → score pipeline worker |
| Toplayıcı | `collector` | Dış kaynaklardan veri çeken worker |
| Yönetici | `admin` | Sistem yönetimi rolü — tam erişim |
| Görüntüleyici | `viewer` | Salt-okuma kullanıcı rolü |
| Sohbet geçmişi | `chat_history` | Chatbot soru/yanıt kayıtları |
| İçerik parçası | `content_chunk` | RAG pipeline için embedding'e dönüştürülmüş metin parçası |

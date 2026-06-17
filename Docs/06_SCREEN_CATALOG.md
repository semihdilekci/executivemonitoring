# 06 — Ekran Kataloğu

> **Platform:** YıldızHolding Global Intelligence Platform (YGIP)
> **Kapsam:** MVP-0 tüm ekranlar — web (Next.js) ve mobil (React Native) ortak spesifikasyon
> **Görsel referans:** `Docs/YGIP_screen_reference_mockup.html` — **admin** layout (sol sidebar) ve içerik bileşenleri (Executive Brief, digest kartları, detay) için referans. **Viewer** layout'ta sol sidebar yoktur; üstte `PillNav` kullanılır (bkz. [Rol Bazlı Navigasyon](#rol-bazlı-navigasyon)).

---

## Ekran Haritası

```mermaid
flowchart TD
    START["Uygulama Açılış"] --> AUTH_CHECK{"Token var mı?"}
    AUTH_CHECK -->|"Hayır"| S_LOGIN["S-LOGIN\nGiriş Ekranı"]
    AUTH_CHECK -->|"Evet"| S_HOME["S-HOME\nAna Sayfa"]

    S_LOGIN -->|"Başarılı"| S_HOME
    S_LOGIN -->|"Şifre sıfırla linki"| S_RESET["S-RESET-PW\nŞifre Sıfırlama"]
    S_RESET -->|"Başarılı"| S_LOGIN

    S_HOME --> S_DIGESTS["S-DIGESTS-LIST\nBültenler"]
    S_HOME --> S_CHAT["S-CHATBOT\nAI Chatbot"]
    S_DIGESTS -->|"Kart tıkla"| S_DETAIL["S-DIGEST-DETAIL\nBülten Detay"]
    S_DETAIL -->|"AI'ya sor FAB"| S_CHAT

    S_HOME -->|"admin sidebar"| ADMIN_GROUP["Admin Ekranları"]
    ADMIN_GROUP --> S_USERS["S-ADMIN-USERS"]
    ADMIN_GROUP --> S_SOURCES["S-ADMIN-SOURCES"]
    ADMIN_GROUP --> S_PROMPTS["S-ADMIN-PROMPTS"]
    ADMIN_GROUP --> S_APIKEYS["S-ADMIN-API-KEYS"]
    ADMIN_GROUP --> S_NOTIF["S-ADMIN-NOTIFICATIONS"]
    ADMIN_GROUP --> S_CHATHIST["S-ADMIN-CHAT-HISTORY"]
    ADMIN_GROUP --> S_AUDIT["S-ADMIN-AUDIT-LOGS"]

    AUTH_CHECK -->|"Token expired"| S_SESSION["S-SESSION-EXPIRED\nOturum Sona Erdi"]
    S_SESSION --> S_LOGIN
```

## Layout Tipleri

| Layout | Açıklama | Kullanıldığı Ekranlar | Rol |
|--------|----------|----------------------|-----|
| **Auth** | Tam sayfa, navigasyon yok, ortalanmış kart | S-LOGIN, S-RESET-PW | Herkes (public) |
| **Dashboard-Viewer** | Üstte `PillNav` + tam genişlik içerik; **sol sidebar yok** | S-HOME, S-DIGESTS-LIST, S-DIGEST-DETAIL, S-CHATBOT | `viewer` |
| **Dashboard-Admin** | Sol sidebar (Ana Menü + Yönetim) + içerik alanı (`margin-left: 260px`) | S-HOME, S-DIGESTS-LIST, S-DIGEST-DETAIL, S-CHATBOT, tüm S-ADMIN-* | `admin` |
| **Minimal** | Sadece mesaj + aksiyon butonu, navigasyon yok | S-404, S-500 | Herkes |
| **Modal/Overlay** | Mevcut ekranın üzerinde, arka plan karartılı | S-SESSION-EXPIRED, S-CONFIRM-DIALOG, S-ADMIN-*-CREATE/EDIT formları | Authenticated |

## Rol Bazlı Navigasyon

Navigasyon shell'i JWT `role` claim'ine göre **tamamen farklı** render edilir. İki layout aynı anda görünmez.

| Rol | Shell | Navigasyon öğeleri |
|-----|-------|-------------------|
| **viewer** | `PillNav` (üst, sticky) + sağ üst kullanıcı menüsü (avatar, çıkış) | Ana Sayfa (`/`), Bültenler (`/digests`), AI Chatbot (`/chatbot`) |
| **admin** | Sol `Sidebar` (mockup referansı) | Ana Menü: Ana Sayfa, Bültenler, AI Chatbot · Yönetim: Kullanıcılar, Kaynaklar, Prompt Şablonları, API Yönetimi, Bildirimler, Sohbet Geçmişi, Denetim Logu · Altta avatar + rol |

**Güvenlik:** Viewer layout'unda `Sidebar` ve admin route linkleri **DOM'da render edilmez**. Admin layout'unda `PillNav` render edilmez. Backend `/admin/*` guard'ı değişmez.

**Mobil (React Native):** Viewer → bottom tab: Ana Sayfa, Bültenler, Chatbot. Admin → aynı tab'lar + Yönetim tab'ı (veya drawer).

### PillNav (viewer web)

React Bits `PillNav` pattern'i temel alınır; Next.js App Router'a uyarlanır (`next/link`, `usePathname`). Bağımlılık: `gsap` (npm bundle; `prefers-reduced-motion: reduce` → animasyonlar kapalı).

| Prop / davranış | Değer |
|-----------------|-------|
| `items` | Sabit 3 link — admin route içermez |
| Renkler | `theme.ts` YGIP token'ları (navy `baseColor`, altın/beyaz pill varyantları) |
| Konum | `sticky top-0`, tam genişlik header bandı (floating `absolute` değil) |
| Aktif sayfa | `activeHref` = `usePathname()`; `/digests/[id]` iken `activeHref="/digests"` |
| Logo | YGIP yıldız logosu; tıklanınca `/` |
| Metinler | Türkçe, sentence case (uppercase zorunlu değil) |

## Ortak Bileşenler

Authenticated ekranlarda kullanılan paylaşımlı bileşenler (rol bazlı görünürlük notu ile):

| Bileşen | Açıklama | Davranış | Rol |
|---------|----------|----------|-----|
| **Sidebar** | Sol navigasyon (navy). Mockup ile birebir. Üstte YGIP logosu + "Global Intelligence". Ana Menü + Yönetim bölümleri. Altta avatar + isim + rol. Mobilde hamburger → overlay. | Aktif sayfa highlight | **admin only** |
| **PillNav** | Üst yatay pill navigasyon. Logo + 3 link. Mobilde hamburger popover. | `activeHref` ile aktif pill | **viewer only** |
| **UserMenu** | Avatar + çıkış (ve isteğe bağlı profil). | PillNav/Sidebar dışında sağ üst | Authenticated |
| **AdminTopbar** | Admin mobilde: hamburger (sidebar aç) + sayfa başlığı + bildirim ikonu. Masaüstünde sidebar açıkken görünmez. | — | **admin only** |
| **Toast** | Başarı (yeşil) / hata (kırmızı) / bilgi (mavi) bildirimi. Sağ üstte belirir, 3 saniye sonra otomatik kapanır. | Kapatma butonu ile erken kapatılabilir. | Authenticated |
| **ConfirmDialog** | Tehlikeli aksiyonlarda (silme, pasif yapma) onay modalı. Başlık + açıklama + "İptal" + "Onayla" (kırmızı) butonları. | Escape veya dış tıklama ile kapatılır. | Authenticated |
| **EmptyState** | Veri yokken gösterilen bileşen. İkon + mesaj + aksiyon butonu (opsiyonel). | Her liste ekranında ilgili boş durum mesajı farklıdır. | Authenticated |
| **LoadingSkeleton** | Veri yüklenirken gerçek layout'u taklit eden gri bloklar. | Sayfa bazlı: DigestListSkeleton, UserTableSkeleton vb. CLS engellenir. | Authenticated |
| **ErrorView** | API hatası gösterimi. Hata ikonu + mesaj + "Tekrar Dene" butonu. | Retry tıklanınca ilgili React Query refetch tetiklenir. | Authenticated |
| **DataTable** | Sıralama ve filtreleme destekli tablo. Header'da kolon bazlı sort toggle, üstte filtre chip'leri. | Admin listelerinde kullanılır. Cursor-based "Daha fazla yükle" butonu ile pagination. | **admin only** |
| **ReadToggle** | 👁 göz ikonu butonu. Tıklanınca okundu ↔ okunmadı arası geçiş. Okundu: yeşil border + dolgu. Okunmadı: gri border. | Digest kartlarında sağ alt köşede, kompakt listede satır sonunda. Kullanıcı bazlı `user_digest_reads` tablosuna yazılır. | Authenticated |

---

## Grup 1 — Auth Ekranları

---

### S-LOGIN — Giriş Ekranı

**Route:** `/login` · **Layout:** Auth · **Erişim:** Public · **Mobil:** LoginScreen

**Amaç:** Kullanıcının email ve şifre ile sisteme giriş yapması.

**Görsel yapı:**
Tam sayfa, dikey ortalanmış beyaz kart. Üstte YGIP logosu (altın yıldız + "YGIP" + "Global Intelligence Platform" alt başlık). Kart içinde: email input, şifre input (göster/gizle toggle), "Giriş Yap" butonu (primary, tam genişlik), altta küçük "Şifre sıfırlama talebiniz için yöneticinize başvurun" bilgi metni. Arka plan: hafif gradient (navy-900 → navy-800).

**Form alanları:**

| Alan | Tip | Validation | Hata mesajı |
|------|-----|-----------|-------------|
| E-posta | `email` input, autofocus | `z.string().email()` | "Geçerli bir e-posta adresi girin." |
| Şifre | `password` input, göster/gizle toggle | `z.string().min(1)` | "Şifre alanı boş bırakılamaz." |

**State'ler:**

| State | Görünüm |
|-------|---------|
| Varsayılan | Boş form, "Giriş Yap" butonu aktif |
| Yükleniyor | Buton disabled, spinner gösterir, input'lar disabled |
| Hata — geçersiz kimlik | Form üstünde kırmızı banner: "E-posta veya şifre hatalı." Input'lar temizlenmez. |
| Hata — hesap pasif | Kırmızı banner: "Hesabınız pasif durumda. Yöneticinize başvurun." |
| Hata — rate limit | Kırmızı banner: "Çok fazla deneme. Lütfen X saniye bekleyin." Buton disabled, geri sayım gösterilir. |
| Hata — ağ | Kırmızı banner: "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin." |

**API mapping:**
- Form submit → `POST /api/v1/auth/login` `{ email, password }`
- Başarılı → access_token memory'e, refresh_token httpOnly cookie'ye (web) / SecureStore'a (mobil), AuthContext güncellenir, `/` adresine redirect
- Başarısız → ilgili hata state'i gösterilir

**Edge case'ler:**
- Giriş yapmış kullanıcı `/login`'e gelirse → otomatik `/` redirect (middleware guard).
- Enter tuşu form submit tetikler.
- Şifre alanında yapıştırma (paste) izinlidir.
- Caps Lock açıksa şifre alanı altında "Caps Lock açık" uyarısı gösterilir.

---

### S-RESET-PW — Şifre Sıfırlama

**Route:** `/reset-password/[token]` · **Layout:** Auth · **Erişim:** Public (geçerli token ile) · **Mobil:** ResetPasswordScreen

**Amaç:** Admin tarafından gönderilen tek kullanımlık link ile yeni şifre belirleme.

**Görsel yapı:**
S-LOGIN ile aynı layout (tam sayfa, ortalanmış kart). Kart içinde: "Yeni Şifre Belirle" başlık, yeni şifre input, şifre tekrar input, şifre politikası göstergesi (min 8 karakter, 1 büyük harf, 1 rakam — her kural karşılandıkça yeşile döner), "Şifreyi Güncelle" butonu.

**Form alanları:**

| Alan | Tip | Validation | Hata mesajı |
|------|-----|-----------|-------------|
| Yeni şifre | `password`, göster/gizle | min 8, 1 büyük harf, 1 rakam | İlgili kural kırmızı kalır |
| Şifre tekrar | `password` | İlk alan ile eşleşme | "Şifreler eşleşmiyor." |

**State'ler:**

| State | Görünüm |
|-------|---------|
| Token doğrulanıyor | Skeleton kart, spinner |
| Token geçerli | Form gösterilir |
| Token geçersiz/expired | Hata kartı: "Bu şifre sıfırlama linki geçersiz veya süresi dolmuş. Yöneticinizden yeni bir link talep edin." + "Giriş Sayfasına Dön" butonu |
| Başarılı | Yeşil başarı kartı: "Şifreniz güncellendi." + "Giriş Yap" butonu (3 saniye sonra otomatik redirect) |

**API mapping:**
- Sayfa yüklendiğinde → `POST /api/v1/auth/validate-reset-token` `{ token }` — token geçerliliği kontrol
- Form submit → `POST /api/v1/auth/reset-password` `{ token, new_password }` — şifre güncelleme
- Başarılı → login sayfasına redirect

---

### S-SESSION-EXPIRED — Oturum Sona Erdi

**Render:** Modal overlay · **Layout:** Mevcut sayfa üzerinde · **Tetikleyici:** Token refresh başarısız (refresh token expired)

**Amaç:** Kullanıcıyı oturumunun sona erdiği konusunda bilgilendirmek ve login'e yönlendirmek.

**Görsel yapı:**
Arka plan karartılı overlay üzerinde ortalanmış küçük beyaz kart. Kilit ikonu + "Oturumunuz Sona Erdi" başlık + "Güvenliğiniz için oturumunuz otomatik olarak sonlandırıldı. Devam etmek için yeniden giriş yapın." açıklama + "Giriş Yap" butonu (primary, tam genişlik).

**Davranış:**
- Modal kapanmaz (X butonu yok, dış tıklama kapatmaz, Escape çalışmaz) — tek çıkış "Giriş Yap" butonu.
- Tıklanınca AuthContext temizlenir, React Query cache temizlenir, `/login` adresine redirect.
- Mobilde aynı davranış: overlay modal, tek buton.

---

### S-404 — Sayfa Bulunamadı

**Route:** Eşleşmeyen tüm route'lar · **Layout:** Minimal · **Erişim:** Herkes

**Görsel yapı:**
Tam sayfa, dikey ortalanmış. Büyük "404" sayısı (light gray, çok büyük font), altında "Aradığınız sayfa bulunamadı" mesajı, altında "Ana Sayfaya Dön" butonu (primary).

**Davranış:**
- Giriş yapmış kullanıcı → "Ana Sayfaya Dön" butonu `/` adresine yönlendirir.
- Giriş yapmamış kullanıcı → "Giriş Sayfasına Dön" butonu `/login` adresine yönlendirir (auth durumuna göre buton metni değişir).

---

### S-500 — Sistem Hatası

**Render:** Next.js `error.tsx` global error boundary · **Layout:** Minimal · **Erişim:** Herkes

**Görsel yapı:**
Tam sayfa, dikey ortalanmış. Uyarı ikonu (kırmızı), "Bir şeyler yanlış gitti" başlık, "Teknik bir sorun yaşanıyor. Lütfen daha sonra tekrar deneyin." açıklama, "Tekrar Dene" butonu (sayfayı yeniler) + "Ana Sayfaya Dön" butonu.

**Davranış:**
- "Tekrar Dene" → `window.location.reload()` çağırır.
- Development modunda hata detayı (stack trace) küçük fontla gösterilir; production'da gizlenir.
- React error boundary yakalar — component tree crash'i tüm sayfayı çökertmez, bu ekran gösterilir.

---

## Grup 2 — Viewer Ekranları

> **Layout:** `viewer` → `Dashboard-Viewer` (PillNav). `admin` → aynı ekran içerikleri `Dashboard-Admin` (sidebar) ile gösterilir.
>
> S-HOME, S-DIGESTS-LIST ve S-DIGEST-DETAIL içerik bileşenleri için `Docs/YGIP_screen_reference_mockup.html` referans alınır (admin sidebar layout). Viewer'da içerik tam genişliktir.

---

### S-HOME — Ana Sayfa

**Route:** `/` · **Layout:** Dashboard-Viewer (viewer) / Dashboard-Admin (admin) · **Erişim:** Authenticated · **Mobil:** HomeScreen

**Amaç:** Kullanıcının güncel durumu 10 saniyede kavraması: bugün ne bilmem gerekiyor, Yıldız'ı etkileyen öne çıkan gelişmeler neler. Bülten listesinin tamamı **S-DIGESTS-LIST** (`/digests`) ekranındadır.

**Görsel yapı — yukarıdan aşağıya:**

#### 1. Executive Brief (Günün Özeti)

Ekranın en üstünde koyu navy gradient kart. Tam genişlik, köşeleri yuvarlatılmış (radius-xl). Sağ üst köşede dekoratif altın radial gradient.

İçerik yapısı:
- **Header satırı:** ⭐ ikon + "GÜNÜN ÖZETİ" label (gold, uppercase, küçük font) + sağda tarih/saat ("16 Haziran 2026, Pazartesi — 09:15")
- **Özet paragraf:** 2-4 cümle. Beyaz metin, önemli sayılar ve gelişmeler altın renkte (`.hl` class) vurgulanmış.
- **İstatistik bandı:** Alt kenarda ince border-top ile ayrılmış. 4 metrik yan yana: kaynak sayısı, yeni bülten sayısı, işlenen haber sayısı, Yıldız etkili gelişme sayısı.

Veri kaynağı: `GET /api/v1/briefs/today` → `{ summary, stats, generated_at }`

Mobil farklılık: İstatistik bandı 2x2 grid.

#### 2. Okunmamış Bülten Özeti (kompakt)

En fazla **3 okunmamış** digest için küçük teaser kartları (tek satır başlık + tip badge). Kart tıklanınca detay sayfasına gider.

Section footer: "Tüm bültenleri gör →" linki → `/digests` (PillNav'da Bültenler aktif olur).

API: `GET /api/v1/digests?is_read=false&limit=3`

#### 3. Chatbot Kısayolu

Sayfanın altında beyaz kart: AI ikon + text input + gönder. Enter/gönder → `/chatbot?q=...` yönlendirmesi. Inline yanıt gösterilmez.

#### State'ler

| State | Görünüm |
|-------|---------|
| Yükleniyor | Executive Brief skeleton + en fazla 3 küçük kart skeleton |
| Veri yok | Executive Brief yerine bilgi kartı + EmptyState |
| Günün özeti henüz üretilmedi | Brief alanında "Günün özeti hazırlanıyor..." |
| Ağ hatası | ErrorView + "Tekrar Dene" |

---

### S-DIGESTS-LIST — Bültenler

**Route:** `/digests` · **Layout:** Dashboard-Viewer / Dashboard-Admin · **Erişim:** Authenticated · **Mobil:** DigestsScreen (tab: Bültenler)

**Amaç:** Tüm haftalık bültenlerin listelenmesi, okundu/okunmadı takibi ve detaya geçiş.

**Görsel yapı — yukarıdan aşağıya:**

#### 1. Sayfa başlığı

"H1: Bültenler" + isteğe bağlı filtre chip'leri (tümü / Türk Medyası / FMCG / Strateji).

#### 2. Yeni Bültenler Bölümü

Section header: "Yeni Bültenler" + okunmamış sayı badge'i + ince gri çizgi.

**3 büyük digest kartı** dikey sıra (tek kolon, tam genişlik). Her kart:

**Kart üst (tıklanabilir → `/digests/[id]`):**
- Digest tipi badge (FMCG yeşil, Strateji amber, Türk Medyası mavi; emoji + tip adı)
- Başlık (h3, bold), teaser (2-3 cümle), meta: tarih · kaynak sayısı · bölüm sayısı

**Kart alt — Yıldız Etki Analizi (varsayılan görünür):**
- gold-50 bant, "YILDIZ HOLDİNG İÇİN ETKİ" label, `digest.yildiz_impact_summary` paragrafı

**ReadToggle:** Sağ alt 👁; okunmadı → sol 3px altın border + sağ üst altın nokta. Okundu → yeşil border.

API: `GET /api/v1/digests?limit=20` · `POST/DELETE /api/v1/digests/{id}/read`

Sıralama: `is_read=false` üstte büyük kart; `published_at desc`.

#### 3. Önceki Bültenler Bölümü

Kompakt liste: tip badge, başlık (truncate), tarih, ReadToggle. İlk 10 okunmuş + "Daha fazla yükle" (cursor pagination).

#### State'ler

| State | Görünüm |
|-------|---------|
| Yükleniyor | 3 digest kart skeleton + liste skeleton |
| Veri yok | EmptyState: "Henüz bülten yok" |
| Ağ hatası | ErrorView |

---

### S-DIGEST-DETAIL — Bülten Detay

**Route:** `/digests/[id]` · **Layout:** Dashboard-Viewer / Dashboard-Admin · **Erişim:** Authenticated · **Mobil:** DigestDetailScreen

**Amaç:** Yöneticinin bülteni 3-5 dakikada taraması, ilgilendiği bölüme drill-down etmesi, Yıldız etkisini anlaması ve isterse haberleri derinlemesine analiz ettirmesi.

**Görsel yapı — yukarıdan aşağıya:**

#### 1. Progress Bar

Sayfanın en üstünde 3px scroll progress çubuğu. Altın gradient dolgu.

**Konum (rol bazlı):**
- **viewer:** `left: 0; right: 0` (tam genişlik, sidebar yok)
- **admin:** `left: 260px; right: 0` (sidebar offset)

Hesaplama: `(window.scrollY / (document.scrollHeight - window.innerHeight)) * 100`

#### 2. Geri Navigasyon

Sol üstte "← Bültenler" link butonu → `/digests`. PillNav'da **Bültenler** aktif kalır.

#### 3. İki Kolonlu Layout

Sol kolon (200px, sticky): İçindekiler navigasyonu.
Sağ kolon (flex): İçerik alanı.

Mobilde tek kolon: İçindekiler üstte horizontal scrollable chip/tab olarak gösterilir.

#### 4. İçindekiler (TOC) — Sol Kolon

Sticky pozisyonda (scroll ederken sabit kalır, top: 24px).

Başlık: "İÇİNDEKİLER" (gri, uppercase, küçük font).

Her bölüm bir tıklanabilir satır:
- Sol kenarında 2px transparent border (aktif olunca altın renk).
- Bölüm adı (küçük font, gri; aktif olunca koyu navy, bold).
- Yıldız etkisi olan bölümlerin adının solunda 6px altın nokta (impact-dot) gösterilir.

Scroll spy: Kullanıcı sayfayı scroll ettikçe viewport'a giren bölümün TOC satırı otomatik active olur. Tıklayınca smooth scroll ile ilgili bölüme gider.

#### 5. Hero Kartı — İçerik Alanı Üstü

Beyaz kart, büyük border-radius. İçerik:
- Digest tipi badge (renkli).
- **Başlık** (h1, 22px, extra bold). Bültenin ana başlığı.
- **Dönem bilgisi:** "9 – 15 Haziran 2026 · 38 kaynaktan derlendi · 5 bölüm"
- **TL;DR kutusu:** Açık gri arka plan, sol kenarında 3px altın border. Üstte "ÖZET" label (altın). 3-4 cümlelik bülten özeti. Yönetici zamanı kısıtlıysa sadece bunu okuyup çıkabilir.
- **İstatistik satırı:** Kaynak sayısı, haber sayısı, Yıldız etkili sayısı, oluşturulma zamanı.

API mapping: `GET /api/v1/digests/{id}` → tam digest objesi (sections array dahil).

#### 6. Bölüm Kartları (Tekrarlayan Yapı)

Her bölüm ayrı bir beyaz kart. Kartlar dikey sıralı, aralarında 16px boşluk. Her kartın `id` attribute'u var (scroll spy ve anchor link için).

Bölüm kartı iç yapısı:

**a) Bölüm başlığı:** Solda gri numara ("01"), yanında başlık (bold, 16px).

**b) Bölüm özeti:** 2-3 cümle, gri metin. Bölümün ana mesajını özetler.

**c) Yıldız Etki Kutusu (bölüm seviyesi — varsa, default görünür):**
Altın arka planlı (gold-50) kutu, altın border. Sol üstte ★ ikon. "YILDIZ HOLDİNG İÇİN ETKİ" label. 2-3 cümle somut, aksiyon odaklı analiz. Bu kutu digest üretimi sırasında LLM tarafından yazılır, her bölüm için ayrı. Tüm bölümlerde olmak zorunda değil — yalnızca Yıldız'ı doğrudan ilgilendiren bölümlerde bulunur. Veri: `section.yildiz_impact` alanı (null ise kutu render edilmez).

**d) Haber kartları (collapse/expand):**

Her haber ayrı bir kart. Varsayılan: collapsed (yalnızca başlık ve kaynak görünür). İlk haber expanded olarak açılır.

Collapsed görünüm:
- Sol kenarında ▶ genişletme ikonu (tıklayınca 90° döner).
- Haber başlığı (bold, 13.5px).
- Kaynak adı (mavi, bold) + yayın tarihi (gri).

Expanded görünüm (collapse alanına ek):
- AI özet paragrafı (1-3 cümle). Haberin AI tarafından üretilmiş özeti.
- "Kaynağa git ↗" linki (mavi, dış link — yeni sekmede açılır).
- **"★ Yıldız'ı nasıl etkiler?" butonu** (altın border, küçük). Tıklanmadıkça LLM çağrısı yapılmaz. Tıklanınca:
  1. Butonun altında altın kutu belirir, "Analiz ediliyor..." typing animasyonu gösterilir.
  2. Backend'e `POST /api/v1/chatbot/ask` `{ question: "Bu haberin Yıldız Holding'i nasıl etkilediğini analiz et: [haber başlığı + özet]", context_article_id: article_id }` gönderilir.
  3. LLM yanıtı gelince typing animasyonu yerine analiz metni gösterilir.
  4. Tekrar tıklayınca kutu kapanır/açılır (toggle). LLM tekrar çağrılmaz — ilk yanıt cache'lenir (React Query mutation cache).

Mobil farklılık: Aynı collapse/expand mantığı. Haber kartları tam genişlik.

#### 7. Chatbot FAB (Floating Action Button)

Sağ altta sabit 52px yuvarlak buton. Navy gradient arka plan, altın ✦ sembol. Yalnızca digest detail sayfasında görünür (home'da chatbot quick input zaten var).

Tıklayınca `/chatbot` sayfasına navigate. Opsiyonel: digest context'ini chatbot'a taşıma (query param: `?digest_id=142`), böylece chatbot bu bülteni bağlam olarak kullanır.

#### 8. Alt Navigasyon

Sayfa sonunda ince gri border-top üzerinde üç link: "← Önceki Bülten" (varsa), "Bültenler" (ortada → `/digests`), "Sonraki Bülten →" (varsa).

#### State'ler

| State | Görünüm |
|-------|---------|
| Yükleniyor | Hero skeleton + 3 bölüm skeleton kartı |
| Digest bulunamadı | 404 sayfasına redirect |
| Ağ hatası | ErrorView |
| Yıldız analizi yükleniyor (haber bazlı) | Haber kartı içinde altın kutu, typing animasyonu |
| Yıldız analizi hatası | Altın kutu içinde: "Analiz şu anda yapılamıyor. Daha sonra tekrar deneyin." |

---

### S-CHATBOT — AI Chatbot

**Route:** `/chatbot` · **Layout:** Dashboard-Viewer / Dashboard-Admin · **Erişim:** Authenticated · **Mobil:** ChatbotScreen

**Amaç:** Kullanıcının platform veritabanındaki tüm içerik üzerinde serbest soru sorması ve AI destekli yanıt alması.

**Görsel yapı:**

Tam yükseklik mesajlaşma arayüzü (nav shell altında kalan alanı doldurur — viewer: PillNav altı; admin: sidebar sağı). Üç bölüm:

**a) Mesaj alanı (scrollable, flex-grow):**
Sohbet baloncukları halinde mesajlar. Kullanıcı mesajları sağda (navy arka plan, beyaz metin), AI yanıtları solda (beyaz arka plan, gri border). Her AI yanıtının altında kaynak referansları listesi (varsa): kaynak adı (tıklanabilir link), yayın tarihi, relevance score badge.

Boş durum (henüz mesaj yoksa): Ortada AI sembolü + "YGIP AI Asistan" başlık + "Platform veritabanındaki tüm içerik üzerinde soru sorabilirsiniz." açıklama + 3-4 örnek soru chip'i ("Kakao fiyatları neden düştü?", "Son hafta hangi regülasyon değişiklikleri oldu?", "FMCG sektöründe M&A aktivitesi nasıl?"). Chip'lere tıklayınca soru otomatik gönderilir.

**b) Input alanı (altta sabit):**
Sol tarafta text input (tam genişlik, placeholder: "Sorunuzu yazın..."), sağda gönder butonu (navy daire). Enter ile gönderim. Shift+Enter yeni satır.

**c) AI yanıt akışı:**
Soru gönderildiğinde:
1. Kullanıcı mesajı anında sağda baloncuk olarak görünür.
2. Solda AI baloncuğu belirir, typing animasyonu ("...") gösterilir.
3. Yanıt gelince typing yerine metin + kaynak referansları gösterilir.
4. Yanıt altında küçük gri metin: kullanılan token sayısı (opsiyonel, admin'e görünür).

**Query parameter entegrasyonu:**
- `/chatbot?q=Kakao+fiyatları` → sayfa açıldığında soru otomatik gönderilir.
- `/chatbot?digest_id=142` → sistem prompt'una ilgili digest context eklenir, "Bu bülten hakkında sorular sorabilirsiniz" bilgi mesajı gösterilir.

**API mapping:**
- Soru gönder → `POST /api/v1/chatbot/ask` `{ question }` → `{ answer, sources: [{ title, url, published_at, relevance_score }], token_used }`
- Her soru/yanıt backend'de `chat_history` tablosuna otomatik yazılır.

**State'ler:**

| State | Görünüm |
|-------|---------|
| Boş sohbet | Örnek sorular ile karşılama ekranı |
| Yanıt bekleniyor | Typing animasyonu, input disabled, gönder butonu disabled |
| Yanıt geldi | AI baloncuğu + kaynak referansları |
| Hata | AI baloncuğu içinde kırmızı metin: "Yanıt üretilemedi. Lütfen tekrar deneyin." + "Tekrar Dene" butonu (aynı soruyu yeniden gönderir) |
| Rate limit | Toast: "Çok fazla soru gönderildi. Lütfen biraz bekleyin." |

**Mobil farklılık:** Tam ekran mesajlaşma deneyimi. Input alanı keyboard açıldığında yukarı kayar (KeyboardAvoidingView). Kaynak referansları tıklanabilir chip'ler halinde (in-app browser ile açılır).

---

### S-EMPTY-STATES — Boş Durum Ekranları

Her liste ekranında veri yokken gösterilen özelleştirilmiş boş durum bileşenleri. EmptyState bileşeni kullanılır: ikon + başlık + açıklama + aksiyon butonu (opsiyonel).

| Ekran | İkon | Başlık | Açıklama | Aksiyon |
|-------|------|--------|----------|---------|
| S-HOME (brief yok) | 📊 | Günün özeti hazırlanıyor | Özet kısa süre içinde oluşturulacak. | — |
| S-DIGESTS-LIST (digest yok) | 📊 | Henüz bülten yok | İlk bülten planlanan zamanda otomatik oluşturulacak. | — |
| S-CHATBOT (sohbet boş) | ✦ | YGIP AI Asistan | Platform veritabanındaki tüm içerik üzerinde soru sorabilirsiniz. | Örnek soru chip'leri |
| S-ADMIN-USERS | 👥 | Henüz kullanıcı eklenmemiş | İlk kullanıcıyı oluşturarak başlayın. | "Kullanıcı Oluştur" butonu |
| S-ADMIN-SOURCES | 📡 | Henüz kaynak eklenmemiş | Veri toplamaya başlamak için ilk kaynağınızı ekleyin. | "Kaynak Ekle" butonu |
| S-ADMIN-PROMPTS | ✏️ | Henüz prompt şablonu yok | AI'ın bülten üretebilmesi için prompt şablonları gerekli. | "Şablon Oluştur" butonu |
| S-ADMIN-API-KEYS | 🔑 | Henüz API key eklenmemiş | AI servislerinin çalışması için en az bir API key gerekli. | "API Key Ekle" butonu |
| S-ADMIN-CHAT-HISTORY | 💬 | Henüz sohbet geçmişi yok | Kullanıcılar chatbot'u kullandıkça sohbet geçmişi burada görünecek. | — |
| S-ADMIN-AUDIT-LOGS | 📋 | Henüz denetim kaydı yok | Sistem olayları otomatik olarak burada loglanacak. | — |
| S-ADMIN-NOTIFICATIONS | 🔔 | Bildirim ayarları yapılandırılmamış | Mail alıcı listesi ve JWT parametrelerini ayarlayın. | "Ayarları Düzenle" butonu |

---

### S-LOADING-SKELETONS — Yükleme İskeletleri

Her ekranın gerçek layout'unu taklit eden skeleton bileşenleri. Gri (#E5E7EB) bloklar hafif shimmer animasyonu ile. CLS (Cumulative Layout Shift) sıfır hedeflenir — skeleton boyutları gerçek içerik boyutlarıyla eşleşir.

| Ekran | Skeleton yapısı |
|-------|----------------|
| S-HOME | Navy gradient kart skeleton (exec brief boyutunda) + 3 adet digest kart skeleton (badge placeholder + 2 satır title + 3 satır teaser + meta satırı + impact bant) |
| S-DIGEST-DETAIL | Hero kart skeleton (badge + title + period + tldr kutusu) + 3 bölüm kart skeleton (title + 2 satır summary + 2 news item placeholder) |
| S-CHATBOT | Ortada AI sembol skeleton + 3 chip placeholder |
| S-ADMIN-USERS | Tablo header skeleton + 5 satır skeleton (avatar daire + 3 kolon metin) |
| S-ADMIN-SOURCES | Tablo header skeleton + 5 satır skeleton (badge + 2 kolon metin + status toggle) |
| S-ADMIN-API-KEYS | 3 adet key kart skeleton (provider badge + maskelenmiş key satırı + metrik placeholder) |
| S-ADMIN-AUDIT-LOGS | Tablo header skeleton + 10 satır skeleton (zaman + event badge + 2 kolon metin) |

Skeleton bileşenleri `LoadingSkeleton` wrapper'ı altında sayfa bazlı export edilir: `DigestListSkeleton`, `DigestDetailSkeleton`, `ChatbotSkeleton`, `UserTableSkeleton`, `SourceTableSkeleton`, `ApiKeysSkeleton`, `AuditLogSkeleton`.

---

## Grup 3 — Admin: Kullanıcı & Kaynak Yönetimi

---

### S-ADMIN-USERS — Kullanıcı Yönetimi

**Route:** `/admin/users` · **Layout:** Dashboard-Admin · **Erişim:** Admin only · **Mobil:** UsersScreen

**Amaç:** Tüm platform kullanıcılarını listelemek, yeni kullanıcı oluşturmak, mevcut kullanıcıları düzenlemek veya pasif yapmak.

**Görsel yapı:**

Sayfa başlığı: "Kullanıcı Yönetimi" + sağ üstte "Kullanıcı Oluştur" butonu (primary).

Altında DataTable bileşeni:

| Kolon | Genişlik | İçerik |
|-------|---------|--------|
| Kullanıcı | flex | Avatar (initials) + tam ad + email (alt satırda gri) |
| Rol | 100px | Badge: `admin` (navy) veya `viewer` (gri) |
| Durum | 100px | Yeşil nokta + "Aktif" veya gri nokta + "Pasif" |
| Son Giriş | 120px | Relatif zaman ("2 saat önce", "3 gün önce") veya "Hiç giriş yapmadı" |
| Oluşturulma | 120px | Tarih (DD.MM.YYYY) |
| İşlem | 80px | ••• menü butonu → Düzenle, Pasif Yap / Aktif Yap |

Filtreleme: Rol dropdown (Tümü / Admin / Viewer), Durum dropdown (Tümü / Aktif / Pasif).
Arama: İsim veya email üzerinde debounced arama (300ms).

API mapping: `GET /api/v1/users?role=&status=&search=&cursor=&limit=20`

**İşlem menüsü (••• tıklayınca dropdown):**
- "Düzenle" → S-ADMIN-USER-EDIT modal açılır.
- "Pasif Yap" → ConfirmDialog: "Bu kullanıcının erişimi kapatılacak. Devam etmek istiyor musunuz?" → Onay sonrası `PUT /api/v1/users/{id}` `{ is_active: false }` → Toast: "Kullanıcı pasif yapıldı." → Tablo yenilenir.
- (Pasif kullanıcıda) "Aktif Yap" → `PUT /api/v1/users/{id}` `{ is_active: true }` → Toast: "Kullanıcı aktif edildi."

Admin kendi hesabını pasif yapamaz — menüde "Pasif Yap" gizlenir.

---

### S-ADMIN-USER-CREATE — Kullanıcı Oluşturma

**Render:** Modal overlay · **Tetikleyici:** "Kullanıcı Oluştur" butonu

**Form alanları:**

| Alan | Tip | Validation | Hata mesajı |
|------|-----|-----------|-------------|
| E-posta | email input | `z.string().email()` | "Geçerli bir e-posta adresi girin." |
| Ad Soyad | text input | `z.string().min(2)` | "Ad soyad en az 2 karakter olmalı." |
| Rol | select: Admin / Viewer | Zorunlu | "Rol seçimi zorunludur." |
| Şifre | password input | min 8, 1 büyük harf, 1 rakam | İlgili kural kırmızı kalır |

Şifre alanı altında politika göstergesi: üç kural satır halinde listelenir, karşılanan kurallar yeşil tik alır.

Footer: "İptal" (ghost buton) + "Oluştur" (primary buton).

API mapping: `POST /api/v1/users` `{ email, full_name, role, password }` → Başarılı: modal kapanır, Toast "Kullanıcı oluşturuldu", tablo yenilenir. Hata (409 email çakışması): form üstünde "Bu e-posta adresi zaten kullanılıyor."

---

### S-ADMIN-USER-EDIT — Kullanıcı Düzenleme

**Render:** Modal overlay · **Tetikleyici:** İşlem menüsünde "Düzenle"

S-ADMIN-USER-CREATE ile aynı form, farklar:
- Email alanı readonly (disabled, gri arka plan). Email değiştirilemez.
- Şifre alanı opsiyonel: boş bırakılırsa mevcut şifre korunur. "Yeni şifre belirle" checkbox'ı tıklanınca şifre alanı açılır.
- Footer: "İptal" + "Güncelle" (primary).

API mapping: `PUT /api/v1/users/{id}` `{ full_name, role, password? }`

---

### S-ADMIN-SOURCES — Kaynak Yönetimi

**Route:** `/admin/sources` · **Layout:** Dashboard-Admin · **Erişim:** Admin only · **Mobil:** SourcesScreen

**Amaç:** Platform veri kaynaklarını yönetmek: ekleme, düzenleme, aktif/pasif yapma, sağlık durumunu izleme.

**Görsel yapı:**

Sayfa başlığı: "Kaynak Yönetimi" + sağ üstte "Kaynak Ekle" butonu (primary).

Filtre bandı: Tip dropdown (Tümü / RSS / Email / API / Gov) + Durum dropdown (Tümü / Aktif / Pasif / Hatalı) + Arama input.

Altında DataTable:

| Kolon | Genişlik | İçerik |
|-------|---------|--------|
| Kaynak | flex | Kaynak adı (bold) + URL/endpoint (alt satırda gri, truncate) |
| Tip | 90px | Badge: RSS (mavi), Email (mor), API (turuncu), Gov (yeşil) |
| Kategori | 100px | Etiketler: macro, fmcg, finance, strategy, regulatory (küçük chip'ler) |
| Durum | 80px | Toggle switch (aktif/pasif) |
| Sağlık | 60px | Renkli nokta: yeşil (sorunsuz), sarı (retry yaşandı), kırmızı (başarısız) |
| Güvenilirlik | 80px | 0-10 arası sayı + mini bar göstergesi |
| Son Çekim | 120px | Relatif zaman |
| İşlem | 80px | ••• menü → Düzenle, Sil |

**Sağlık göstergesi detayı:** Renkli noktaya hover yapınca tooltip: "Son 24 saat: 96 başarılı, 0 hata" (yeşil) veya "Son 24 saat: 90 başarılı, 6 retry, 2 başarısız — Son hata: Connection timeout (14:32)" (kırmızı).

**Toggle switch davranışı:** Tıklayınca anında `PUT /api/v1/sources/{id}` `{ is_active: toggle }` gönderilir. Optimistic update — başarısızsa geri alınır ve Toast hata gösterilir.

**Toplu işlem:** Tablo başında checkbox ile çoklu seçim. Seçim yapılınca üstte aksiyon bandı belirir: "Seçilenleri Aktif Yap" / "Seçilenleri Pasif Yap" butonları.

**Sil işlemi:** ConfirmDialog: "'{kaynak adı}' kaynağı silinecek. Toplanan makaleler silinmez. Devam etmek istiyor musunuz?" → `DELETE /api/v1/sources/{id}`

API mapping: `GET /api/v1/sources?type=&status=&search=&cursor=&limit=20`

---

### S-ADMIN-SOURCE-CREATE — Kaynak Ekleme

**Render:** Modal overlay · **Tetikleyici:** "Kaynak Ekle" butonu

**Tip seçimi (1. adım):** Modal açıldığında ilk olarak kaynak tipi seçilir. 4 kart halinde: RSS/Atom, E-posta Newsletter, Resmi Kaynak, REST API (MVP-1 etiketi ile). Kart tıklanınca ilgili form açılır.

**RSS/Atom formu:**

| Alan | Tip | Validation |
|------|-----|-----------|
| Kaynak adı | text | Zorunlu, min 2 karakter |
| Feed URL | url input | `z.string().url()`, zorunlu |
| Tarama aralığı | select: 5dk / 15dk / 30dk / 60dk | Varsayılan: 15dk |
| Güvenilirlik ağırlığı | slider 0-10 | Varsayılan: 5 |
| Kategori etiketleri | multi-select chip: macro, fmcg, finance, strategy, regulatory | En az 1 zorunlu |

**E-posta Newsletter formu:**

| Alan | Tip | Validation |
|------|-----|-----------|
| Gönderici adı | text | Zorunlu |
| Gönderici e-posta | email input | Zorunlu, email formatı |
| Beklenen sıklık | select: Günlük / Haftalık / Aylık | Bilgi amaçlı |
| Güvenilirlik ağırlığı | slider 0-10 | Varsayılan: 5 |
| Kategori etiketleri | multi-select chip | En az 1 zorunlu |

**Resmi Kaynak (Gov) formu:**

| Alan | Tip | Validation |
|------|-----|-----------|
| Kaynak adı | text | Zorunlu |
| Endpoint URL | url input | Zorunlu |
| Parse formatı | select: HTML / XML / JSON | Zorunlu |
| Tarama aralığı | select: 15dk / 30dk / 60dk | Varsayılan: 30dk |
| Ingest modu | select: Tüm makaleler (`all`) / Keyword filtreli (`filtered`) | Domain-specific kaynaklar: `all`; geniş kaynaklar: `filtered` (`Docs/04` §8.3) |
| Varsayılan kategori | select: macro / fmcg / finance / strategy / … | `default_category`; ingest_mode `all` kaynaklarda routing |
| Kategori etiketleri | multi-select chip | En az 1 zorunlu |

Footer: "İptal" + "Kaydet" (primary).

Kaynak ekleme sonrası backend URL'ye test çekimi yapar. Başarısızsa uyarı Toast'ı: "Kaynak eklendi ancak ilk bağlantı denemesi başarısız oldu. Lütfen URL'yi kontrol edin." Kaynak yine de eklenir (admin daha sonra düzeltebilir).

API mapping: `POST /api/v1/sources` `{ name, type, config: { feed_url, ingest_mode, default_category, ... }, polling_interval_minutes, category, target_phase }`

---

### S-CONFIRM-DIALOG — Onay Diyaloğu

**Render:** Modal overlay · **Kullanıldığı yerler:** Kullanıcı pasif yapma, kaynak silme, API key silme, prompt aktifleştirme

**Görsel yapı:**
Küçük beyaz modal (max-width 420px). Üstte uyarı ikonu (sarı/kırmızı — işleme göre). Başlık (bold). Açıklama paragrafı (gri). Alt satırda: "İptal" (ghost buton, sol) + "Onayla" / "Sil" / "Pasif Yap" (kırmızı buton, sağ — aksiyon tipine göre etiket değişir).

**Davranış:**
- Escape tuşu veya overlay tıklama → İptal (modal kapanır, işlem yapılmaz).
- "Onayla" butonu tıklanınca → ilgili API çağrısı tetiklenir, buton loading state'e geçer, başarılı olunca modal kapanır ve Toast gösterilir.
- Butonlar click sonrası disabled olur (çift tıklama koruması).

---

## Grup 4 — Admin: AI & İçerik Yönetimi

---

### S-ADMIN-PROMPTS — Prompt Şablon Yönetimi

**Route:** `/admin/prompt-templates` · **Layout:** Dashboard-Admin · **Erişim:** Admin only · **Mobil:** PromptTemplatesScreen

**Amaç:** AI'ın digest üretiminde, chatbot'ta ve enrichment'ta kullandığı prompt şablonlarını yönetmek.

**Görsel yapı:**

Sayfa başlığı: "Prompt Şablon Yönetimi" + "Yeni Şablon" butonu (primary).

DataTable:

| Kolon | Genişlik | İçerik |
|-------|---------|--------|
| Şablon Adı | flex | İsim (bold) + son düzenleme (alt satırda gri) |
| Digest Tipi | 140px | Badge: FMCG (yeşil), Strateji (amber), Türk Medyası (mavi), Chatbot (mor), Enrichment (gri), Günlük Özet (navy) |
| Durum | 80px | Yeşil "Aktif" badge veya gri "Pasif" |
| Versiyon | 60px | v1, v2, v3... |
| Son Düzenleyen | 120px | Kullanıcı adı |
| İşlem | 80px | ••• → Düzenle, Aktif Yap, Versiyon Geçmişi |

"Aktif Yap" yalnızca pasif şablonlarda görünür. Tıklayınca ConfirmDialog: "Bu şablonu aktif yapmak, aynı tipteki mevcut aktif şablonu otomatik olarak pasif yapacak. Devam etmek istiyor musunuz?"

---

### S-ADMIN-PROMPT-EDIT — Prompt Şablon Düzenleme

**Render:** Tam sayfa drawer (sağdan açılır, genişlik %70) veya modal · **Tetikleyici:** "Düzenle" veya "Yeni Şablon"

**Görsel yapı — iki kolonlu:**

Sol kolon (geniş): Düzenleme alanı.
Sağ kolon (dar): Referans paneli.

**Sol kolon — Form:**

| Alan | Tip | Açıklama |
|------|-----|----------|
| Şablon adı | text input | Tanımlayıcı isim |
| Digest tipi | select | FMCG Haftalık / Strateji Haftalık / Türk Medyası Haftalık / Chatbot System / Article Enrichment / Günlük Özet |
| System prompt | textarea (monospace, 6 satır) | LLM system role tanımı |
| User prompt template | textarea (monospace, 20+ satır, resizable) | Jinja2 template — ana prompt gövdesi |
| Yıldız etki talimatı | textarea (monospace, 4 satır) | "Her bölüm için Yıldız Holding'i..." gibi spesifik direktif |
| Çıktı format talimatı | textarea (monospace, 6 satır) | LLM'den beklenen JSON schema açıklaması |
| Max tokens | number input | Varsayılan: 4096 |
| Temperature | slider 0-1, 0.1 adım | Varsayılan: 0.3 (digest) / 0.5 (chatbot) |

**Sağ kolon — Referans paneli:**

Tab'lı yapı:
1. **Değişkenler:** Kullanılabilir Jinja2 placeholder'lar listesi: `{{ articles }}`, `{{ date_range }}`, `{{ digest_type }}`, `{{ section_name }}`, `{{ user_question }}` (chatbot). Her birinin yanında kopyala butonu.
2. **Mevcut aktif:** Aynı digest tipinin şu an aktif olan şablonunun readonly gösterimi. Admin neyi değiştirdiğini karşılaştırabilir.
3. **Versiyon geçmişi:** Önceki versiyonların listesi (tarih + düzenleyen). Tıklayınca o versiyonun içeriği readonly gösterilir. "Bu versiyona geri dön" butonu ile eski versiyonu aktif yapma.

**Footer:** "İptal" + "Test Et" (secondary) + "Kaydet" (primary).

**"Test Et" butonu davranışı:**
1. Tıklayınca drawer altında test paneli açılır.
2. Backend'e `POST /api/v1/prompt-templates/test` `{ system_prompt, user_prompt_template, max_tokens, temperature }` gönderilir.
3. Son 10 makale ile şablon test edilir, LLM çıktısı formatted JSON olarak gösterilir.
4. Token kullanımı gösterilir (test çağrısı `api_usage_logs`'a "test" etiketiyle loglanır).
5. Admin sonuçları inceleyip beğenirse "Kaydet" ile production'a alır.

API mapping: 
- Oluşturma: `POST /api/v1/prompt-templates` 
- Güncelleme: `PUT /api/v1/prompt-templates/{id}` (otomatik yeni versiyon oluşturur)
- Test: `POST /api/v1/prompt-templates/test`

---

### S-ADMIN-API-KEYS — API Key Yönetimi

**Route:** `/admin/api-keys` · **Layout:** Dashboard-Admin · **Erişim:** Admin only · **Mobil:** ApiKeysScreen

**Amaç:** LLM ve embedding API key'lerini yönetmek, token kullanımını izlemek, maliyet kontrolü sağlamak.

**Görsel yapı — üç bölüm:**

#### Bölüm 1: Key Listesi

Sayfa başlığı: "API Key Yönetimi" + "API Key Ekle" butonu (primary).

Key'ler kart formatında (grid, 2 kolon). Her kart:
- **Üst bant:** Provider logosu/badge (Groq mavi, Gemini mor, OpenAI yeşil, Cohere turuncu) + etiket adı + ••• menü (Düzenle, Sil).
- **Maskelenmiş key:** `••••••••••a4Bf` (son 4 karakter görünür). Kopyala butonu yok (güvenlik).
- **Durum:** Aktif/pasif toggle switch.
- **Öncelik sırası:** Round-robin'deki sıra numarası. Sürükle-bırak ile değiştirilebilir.
- **Hızlı metrikler:** Bu ayki token kullanımı (sayı + mini progress bar — aylık limit varsa limite göre doluluk), son kullanım zamanı.
- **Alarm durumu:** Aylık limit belirlenmişse ve %80+ kullanılmışsa sarı uyarı banner, %95+ kırmızı.

**Key ekleme modalı:**

| Alan | Tip | Validation |
|------|-----|-----------|
| Provider | select: Groq / Gemini / OpenAI / Cohere | Zorunlu |
| API Key | password input (yapıştır odaklı) | Zorunlu, min 10 karakter |
| Etiket | text input | Opsiyonel ("Ana Groq hesabı" gibi) |
| Aylık token limiti | number input | Opsiyonel, 0 = limitsiz |

Ekleme sonrası backend test çağrısı yapar. Geçersiz key → uyarı Toast: "Key eklendi ancak doğrulama başarısız. Lütfen kontrol edin."

#### Bölüm 2: Token Kullanım Dashboard'u

Key listesinin altında tam genişlik dashboard alanı.

**Zaman serisi grafik (ana grafik):**
- Çizgi grafik. X ekseni: tarih. Y ekseni: token sayısı.
- Provider bazında renk ayrımı (Groq mavi, Gemini mor).
- Zaman aralığı seçici: Son 7 gün / Son 30 gün / Son 90 gün.
- Hover'da tooltip: tarih + provider + prompt tokens + completion tokens + toplam.

**Fonksiyon bazlı kırılım (pasta grafik):**
- Küçük pasta/donut grafik. Dilimler: Digest Üretimi, Chatbot, Article Enrichment, Günlük Özet, Test Çağrıları.
- Her dilim etiketli yüzde ve token sayısı.

**Key bazlı kırılım tablosu:**

| Kolon | İçerik |
|-------|--------|
| Key | Provider badge + etiket |
| Toplam Token (30 gün) | Sayı |
| Çağrı Sayısı | Sayı |
| Ortalama Token/Çağrı | Sayı |
| Hata Oranı | % (429/503 sayısı / toplam çağrı) |
| Tahmini Maliyet | USD (provider fiyatlandırma tablosu × token) |

**Trend göstergesi:** Sayfanın üstünde küçük kartlar halinde: bu haftanın toplam token kullanımı, geçen haftaya göre değişim (yeşil ↓ azalış, kırmızı ↑ artış, yüzde).

#### Bölüm 3: Round-Robin Durum Monitörü

Küçük durum kartı: "Aktif provider sırası: 1. Groq (Ana) → 2. Gemini (Yedek)" şeklinde sıra gösterimi. Son çağrının hangi provider'a gittiği. Herhangi bir key kota/hata durumundaysa kırmızı uyarı.

Tüm key'ler başarısızsa tam genişlik kırmızı banner: "Tüm LLM provider'lar erişilemez — digest üretimi ve chatbot devre dışı."

API mapping:
- Key listesi: `GET /api/v1/api-keys`
- Key ekleme: `POST /api/v1/api-keys` `{ provider, key, label, monthly_token_limit }`
- Kullanım metrikleri: `GET /api/v1/api-keys/usage?range=30d&group_by=day`
- Fonksiyon kırılımı: `GET /api/v1/api-keys/usage?range=30d&group_by=function`

---

### S-ADMIN-CHAT-HISTORY — Sohbet Geçmişi

**Route:** `/admin/chat-history` · **Layout:** Dashboard-Admin · **Erişim:** Admin only · **Mobil:** ChatHistoryScreen

**Amaç:** Kullanıcıların chatbot'a sorduğu soruları ve aldığı yanıtları incelemek.

**Görsel yapı:**

Sayfa başlığı: "Sohbet Geçmişi".

Filtre bandı: Kullanıcı dropdown (tüm kullanıcılar listesi) + Tarih aralığı picker (başlangıç — bitiş) + Arama (soru metninde).

DataTable:

| Kolon | Genişlik | İçerik |
|-------|---------|--------|
| Kullanıcı | 140px | Avatar + isim |
| Soru | flex | Soru metni (truncate, max 2 satır) |
| Tarih | 120px | Tarih + saat |
| Token | 80px | Kullanılan token sayısı |
| İşlem | 60px | "Detay" butonu |

"Detay" tıklayınca S-CHAT-DETAIL-MODAL açılır.

API mapping: `GET /api/v1/chat-history?user_id=&date_from=&date_to=&search=&cursor=&limit=20`

---

### S-CHAT-DETAIL-MODAL — Sohbet Detay

**Render:** Modal overlay (geniş, max-width 640px) · **Tetikleyici:** Chat history tablosunda "Detay"

**Görsel yapı:**
Modal başlığı: kullanıcı adı + tarih/saat.

İçerik: Mesajlaşma formatında soru (sağda, navy baloncuk) ve yanıt (solda, beyaz baloncuk). Yanıtın altında kaynak referansları listesi (varsa): kaynak adı, URL (tıklanabilir link), yayın tarihi.

Alt bilgi: "Kullanılan token: 1.247" gri metin.

Footer: "Kapat" butonu.

API mapping: `GET /api/v1/chat-history/{id}` → `{ user, question, answer, sources, token_used, created_at }`

---

### S-DIGEST-TRIGGER-CONFIRM — Manuel Digest Tetikleme Onayı

**Render:** Modal overlay · **Tetikleyici:** Digest listesinde (admin görünümü) "Manuel Tetikle" butonu

**Görsel yapı:**
ConfirmDialog varyantı. Başlık: "Manuel Bülten Tetikleme". Açıklama: "Seçilen digest tipini şimdi üretmek üzeresiniz. Bu işlem LLM token harcayacak ve bildirim gönderecektir."

Ek alan: Digest tipi seçici (FMCG Haftalık / Strateji Haftalık / Türk Medyası Haftalık / Günlük Özet).

Checkbox: "Bildirim gönder" (varsayılan: checked). Unchecked yapılırsa digest üretilir ama mail/push gönderilmez (test amaçlı).

Footer: "İptal" + "Üret" (primary). "Üret" tıklanınca loading state, backend `POST /api/v1/digests/trigger` `{ digest_type, send_notification }` → başarılı: Toast "Bülten üretimi başlatıldı. Birkaç dakika içinde hazır olacak." Modal kapanır.

---

## Grup 5 — Admin: Sistem Yönetimi

---

### S-ADMIN-NOTIFICATIONS — Bildirim Yönetimi

**Route:** `/admin/notifications` · **Layout:** Dashboard-Admin · **Erişim:** Admin only · **Mobil:** NotificationsScreen

**Amaç:** Mail alıcı listesi, bildirim zamanlaması ve JWT token sürelerini yönetmek.

**Görsel yapı — üç bölüm kartı:**

#### Bölüm 1: Mail Alıcı Listesi

Beyaz kart. Başlık: "Mail Alıcı Listesi" + "Alıcı Ekle" butonu.

Tablo: Kullanıcı adı, email, bildirim tipleri (chip'ler: Digest, Hata Bildirimi — toggle edilebilir), kaldır butonu.

"Alıcı Ekle" tıklayınca mevcut kullanıcılar listesinden seçim dropdown'u. Aynı kullanıcı birden fazla kez eklenemez.

API mapping: `GET /api/v1/notifications/recipients`, `POST /api/v1/notifications/recipients` `{ user_id, types }`, `DELETE /api/v1/notifications/recipients/{id}`

#### Bölüm 2: Bildirim Zamanlaması

Beyaz kart. Başlık: "Bildirim Zamanlaması".

Her digest tipi için ayrı satır:

| Digest Tipi | Gün | Saat | Durum |
|------------|-----|------|-------|
| Strateji Haftalık | Cuma | 18:00 | Aktif toggle |
| Türk Medyası Haftalık | Cumartesi | 10:00 | Aktif toggle |
| FMCG Haftalık | Cumartesi | 12:00 | Aktif toggle |
| Günlük Özet | Her gün | 09:00 | Aktif toggle |

Gün ve saat alanları inline düzenlenebilir (select dropdown). Değişiklik anında kaydedilmez — altta "Değişiklikleri Kaydet" butonu.

API mapping: `GET /api/v1/settings?group=notification_schedule`, `PUT /api/v1/settings` `{ notification_schedule: {...} }`

#### Bölüm 3: JWT ve Oturum Ayarları

Beyaz kart. Başlık: "Oturum Ayarları".

| Ayar | Tip | Varsayılan | Açıklama |
|------|-----|-----------|----------|
| Access token süresi | number input (dakika) | 60 | Min: 5, Max: 1440 |
| Refresh token süresi | number input (gün) | 30 | Min: 1, Max: 365 |

Uyarı metni: "Bu ayarları değiştirmek mevcut oturumları etkilemez. Yeni oturumlar güncel değerlerle oluşturulur."

Footer: "Değişiklikleri Kaydet" butonu. Tıklayınca ConfirmDialog: "JWT sürelerini değiştirmek üzeresiniz. Devam etmek istiyor musunuz?"

API mapping: `PUT /api/v1/settings` `{ jwt_access_token_expire_minutes, jwt_refresh_token_expire_days }`

---

### S-ADMIN-AUDIT-LOGS — Denetim Logu

**Route:** `/admin/audit-logs` · **Layout:** Dashboard-Admin · **Erişim:** Admin only · **Mobil:** AuditLogsScreen

**Amaç:** Sistem olaylarını kronolojik olarak görüntülemek, filtrelemek ve incelemek.

**Görsel yapı:**

Sayfa başlığı: "Denetim Logu".

Filtre bandı: Olay tipi multi-select (USER_LOGIN, USER_CREATED, SOURCE_CREATED, DIGEST_GENERATED, COLLECTION_ERROR, vb.) + Kullanıcı dropdown + Tarih aralığı picker.

DataTable:

| Kolon | Genişlik | İçerik |
|-------|---------|--------|
| Zaman | 140px | Tarih + saat (DD.MM.YYYY HH:mm) |
| Olay | 160px | Event type badge (renkli: yeşil başarı, mavi bilgi, kırmızı hata) + okunabilir etiket |
| Kullanıcı | 120px | Actor kullanıcı adı (sistem olayları için "Sistem") |
| Hedef | flex | Target type + target ID + açıklama (örn: "Kullanıcı: ali@yildiz.com", "Kaynak: Bloomberg HT RSS") |
| Detay | 60px | Genişletme ikonu (▶) |

Satır genişletme (expand): Tıklayınca satırın altında JSONB payload'u formatted olarak gösterilir. Örnek:
```
{
  "email": "ali@yildiz.com",
  "role": "viewer",
  "previous_role": "admin"
}
```

Sayfalama: Cursor-based, "Daha fazla yükle" butonu. Varsayılan sıralama: en yeni üstte.

Aktif tabloda 90 günlük veri gösterilir. 90 gün öncesi arşivlenmiş — filtre bandında "Arşiv verisi S3'te saklanmaktadır" bilgi notu.

API mapping: `GET /api/v1/audit-logs?event_types=&user_id=&date_from=&date_to=&cursor=&limit=50`

# Manuel Ekran Test Maddeleri — YGIP

> **Platform:** YıldızHolding Global Intelligence Platform (YGIP)  
> **Kapsam:** MVP-0 — kullanıcının tarayıcı üzerinden ekranlarla yapacağı kabul testleri  
> **Referans:** `Docs/06_SCREEN_CATALOG.md`, `Docs/05_FRONTEND_SPEC.md`  
> **Otomatik testler:** Bu belge pytest/CI yerine geçmez; staging veya local ortamda insan gözüyle doğrulama içindir.

---

## 1. Amaç

Bu belge, uygulamanın **ekranlar üzerinden** uçtan uca doğrulanması için adım adım test maddelerini listeler. Her madde:

- **Kim** test eder (admin / viewer)
- **Hangi ekranda** (S-* kodu)
- **Ne yapılır** (adımlar)
- **Ne beklenir** (kabul kriteri)

içerir.

---

## 2. Ön koşullar

| # | Koşul | Doğrulama |
|---|--------|-----------|
| P1 | API çalışıyor | `GET /api/v1/health` veya login denemesi başarılı |
| P2 | Web uygulaması açılıyor | `http://localhost:3000` (veya staging URL) yükleniyor |
| P3 | Seed verisi yüklü | `python scripts/seed.py` çalıştırılmış; en az 1 digest ve günün özeti verisi var |
| P4 | Test hesapları biliniyor | Aşağıdaki tablo |
| P5 | Tarayıcı | Chrome veya Edge güncel sürüm; çerezler etkin |

### Test hesapları (local seed)

| Rol | E-posta | Şifre | Not |
|-----|---------|-------|-----|
| Admin | `admin@ygip.test` | `DevPass1` | Yalnızca local geliştirme |
| Viewer | `viewer1@ygip.test` | `DevPass1` | |
| Viewer | `viewer2@ygip.test` | `DevPass1` | İkinci kullanıcı senaryoları için |

> Production veya staging ortamında admin tarafından oluşturulmuş gerçek hesaplar kullanılır; şifreler bu belgede tutulmaz.

---

## 3. Test kaydı şablonu

Her test oturumu için üst bilgi doldurulur:

| Alan | Değer |
|------|-------|
| Tarih | |
| Ortam | local / staging / prod |
| Tarayıcı | |
| Test eden | |
| Build / commit | |

Sonuç kodları: **G** (Geçti) · **K** (Kaldı) · **B** (Bloklu — ön koşul eksik) · **NA** (Uygulanamaz)

---

## 4. Genel ve çapraz testler

### 4.1 Rol ve navigasyon

| ID | Rol | Adımlar | Beklenen sonuç | Öncelik |
|----|-----|--------|----------------|---------|
| X-01 | Viewer | `viewer1@ygip.test` ile giriş yap | Üstte **PillNav** görünür (Ana Sayfa, Bültenler, AI Chatbot). Sol sidebar **yok** | Kritik |
| X-02 | Viewer | Sayfa kaynağını incele veya geliştirici araçlarında `/admin` linki ara | Admin menü linkleri DOM'da **görünmez** | Kritik |
| X-03 | Viewer | Adres çubuğuna `/admin/users` yaz | Erişim engellenir (403 sayfası veya ana sayfaya yönlendirme) | Kritik |
| X-04 | Admin | `admin@ygip.test` ile giriş yap | Sol **sidebar** görünür: Ana Menü + Yönetim bölümleri | Kritik |
| X-05 | Admin | Sidebar'dan tüm yönetim sayfalarına sırayla git | Her sayfa hatasız yüklenir; aktif menü öğesi vurgulanır | Yüksek |
| X-06 | Admin | Viewer ekranlarına (Ana Sayfa, Bültenler, Chatbot) git | İçerik yüklenir; admin layout (sidebar) korunur | Yüksek |
| X-07 | Her iki rol | Sağ üst kullanıcı menüsünden **Çıkış** | Oturum kapanır, `/login` sayfasına yönlendirilir | Kritik |
| X-08 | Her iki rol | Çıkış sonrası geri tuşu | Korumalı sayfaya erişilemez, login'e yönlendirilir | Yüksek |

### 4.2 Responsive ve erişilebilirlik (temel)

| ID | Rol | Adımlar | Beklenen sonuç | Öncelik |
|----|-----|--------|----------------|---------|
| X-09 | Viewer | Tarayıcı penceresini mobil genişliğe (~375px) daralt | PillNav ve içerik taşmadan görünür; yatay kaydırma yok | Orta |
| X-10 | Admin | Mobil genişlikte sidebar | Hamburger ile menü açılıp kapanır | Orta |
| X-11 | Her iki rol | Tab tuşu ile login formunda gezin | Focus halkası görünür; Enter ile gönderim çalışır | Orta |
| X-12 | Her iki rol | Bir toast bildirimi tetikle (ör. admin'de kayıt kaydet) | Toast sağ üstte belirir, ~3 sn sonra kaybolur | Düşük |

---

## 5. Kimlik doğrulama ekranları

### S-LOGIN — Giriş (`/login`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| AUTH-01 | `/login` aç | YGIP logosu, e-posta ve şifre alanları, "Giriş Yap" butonu görünür | Kritik |
| AUTH-02 | Geçersiz e-posta formatı gir, gönder | "Geçerli bir e-posta adresi girin." hatası | Yüksek |
| AUTH-03 | Boş şifre ile gönder | "Şifre alanı boş bırakılamaz." hatası | Yüksek |
| AUTH-04 | Yanlış şifre ile doğru e-posta dene | "E-posta veya şifre hatalı." banner; alanlar temizlenmez | Kritik |
| AUTH-05 | Doğru admin bilgileri ile giriş | Ana sayfaya yönlendirme; sidebar layout | Kritik |
| AUTH-06 | Doğru viewer bilgileri ile giriş | Ana sayfaya yönlendirme; PillNav layout | Kritik |
| AUTH-07 | Giriş yapmışken `/login` adresine git | Otomatik `/` yönlendirmesi | Yüksek |
| AUTH-08 | Şifre alanında göster/gizle toggle | Şifre metni görünür/gizlenir | Düşük |
| AUTH-09 | 10+ hatalı giriş denemesi (rate limit) | "Çok fazla deneme..." mesajı; buton geçici devre dışı | Orta |

### S-RESET-PW — Şifre sıfırlama (`/reset-password/[token]`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| AUTH-10 | Admin panelinden kullanıcı için şifre sıfırlama linki oluştur | E-posta veya admin arayüzünde tek kullanımlık link üretilir | Yüksek |
| AUTH-11 | Geçerli token ile reset sayfasını aç | Yeni şifre formu görünür; politika göstergesi (8 karakter, büyük harf, rakam) | Kritik |
| AUTH-12 | Zayıf şifre gir | İlgili kural kırmızı kalır; kayıt olmaz | Yüksek |
| AUTH-13 | Şifre ve tekrar uyuşmuyor | "Şifreler eşleşmiyor." hatası | Yüksek |
| AUTH-14 | Geçerli yeni şifre kaydet | Başarı mesajı; login sayfasına yönlendirme | Kritik |
| AUTH-15 | Yeni şifre ile giriş | Başarılı oturum | Kritik |
| AUTH-16 | Aynı reset linkini tekrar kullan | "Link geçersiz veya süresi dolmuş" benzeri hata | Yüksek |
| AUTH-17 | Rastgele/geçersiz token ile sayfa aç | Hata kartı + "Giriş Sayfasına Dön" | Yüksek |

### S-SESSION-EXPIRED — Oturum sona erdi

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| AUTH-18 | Access token süresi dolmuş / refresh başarısız senaryo simüle et | Modal: "Oturumunuz Sona Erdi"; dış tıklama ile kapanmaz | Yüksek |
| AUTH-19 | Modal'da "Giriş Yap" tıkla | Login sayfasına yönlendirme; önceki sayfa cache'i temizlenmiş olmalı | Yüksek |

### S-404 / S-500

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| AUTH-20 | Giriş yapmışken `/olmayan-sayfa` aç | 404 ekranı; "Ana Sayfaya Dön" çalışır | Orta |
| AUTH-21 | Giriş yapmamışken bilinmeyen URL | "Giriş Sayfasına Dön" veya login yönlendirmesi | Orta |

---

## 6. Viewer ekranları (admin de aynı içeriği sidebar ile görür)

### S-HOME — Ana Sayfa (`/`)

| ID | Rol | Adımlar | Beklenen sonuç | Öncelik |
|----|-----|--------|----------------|---------|
| HOME-01 | Viewer | Ana sayfayı aç | **Günün Özeti** (Executive Brief) kartı: özet metin + istatistik bandı (kaynak, bülten, haber, Yıldız etkili sayıları) | Kritik |
| HOME-02 | Viewer | Brief yüklenirken sayfayı yenile | Skeleton iskelet görünür; içerik gelince layout kayması minimum | Orta |
| HOME-03 | Viewer | Okunmamış bülten teaser'ları varsa birine tıkla | İlgili bülten detay sayfasına gider | Yüksek |
| HOME-04 | Viewer | "Tüm bültenleri gör →" linkine tıkla | `/digests` sayfasına gider | Yüksek |
| HOME-05 | Viewer | Alttaki chatbot kısayoluna soru yaz, Enter | `/chatbot?q=...` ile yönlendirme; soru chatbot'ta hazır | Yüksek |
| HOME-06 | Viewer | Veri yok / özet henüz üretilmedi ortamında test | "Günün özeti hazırlanıyor..." veya bilgi kartı | Orta |
| HOME-07 | Admin | Aynı HOME-01–05 maddeleri | İçerik viewer ile aynı; layout sidebar'lı | Yüksek |

### S-DIGESTS-LIST — Bültenler (`/digests`)

| ID | Rol | Adımlar | Beklenen sonuç | Öncelik |
|----|-----|--------|----------------|---------|
| DIG-01 | Viewer | Bültenler sayfasını aç | "Yeni Bültenler" ve "Önceki Bültenler" bölümleri; tip badge'leri (FMCG, Strateji, Türk Medyası) | Kritik |
| DIG-02 | Viewer | Tip filtresi chip'lerini dene (varsa) | Liste ilgili tipe göre filtrelenir | Orta |
| DIG-03 | Viewer | Büyük kartın gövdesine tıkla | `/digests/[id]` detay sayfası açılır | Kritik |
| DIG-04 | Viewer | Kartta **Yıldız Holding için Etki** bandını kontrol et | Özet paragraf görünür (veri varsa) | Yüksek |
| DIG-05 | Viewer | Okunmamış bültende 👁 **ReadToggle** tıkla | Kart okundu olarak işaretlenir (yeşil border); sayfa yenilense bile durum korunur | Kritik |
| DIG-06 | Viewer | Okunmuş bültende ReadToggle ile geri al | Okunmadı durumuna döner | Yüksek |
| DIG-07 | Viewer | "Daha fazla yükle" (önceki bültenler) | Ek kayıtlar listelenir | Orta |
| DIG-08 | Viewer | Hiç bülten yok ortamı | EmptyState: "Henüz bülten yok" | Orta |

### S-DIGEST-DETAIL — Bülten Detay (`/digests/[id]`)

| ID | Rol | Adımlar | Beklenen sonuç | Öncelik |
|----|-----|--------|----------------|---------|
| DET-01 | Viewer | Bir bülten detayını aç | Hero: başlık, dönem, TL;DR kutusu, istatistik satırı | Kritik |
| DET-02 | Viewer | Sayfayı aşağı kaydır | Üstte scroll progress çubuğu ilerler | Düşük |
| DET-03 | Viewer | Sol **İçindekiler** (TOC) listesinden bölüm seç | İlgili bölüme smooth scroll | Yüksek |
| DET-04 | Viewer | Scroll ile bölüm değiştir | TOC'da aktif bölüm vurgulanır | Orta |
| DET-05 | Viewer | Yıldız etkisi olan bölümde altın etki kutusunu kontrol et | "Yıldız Holding için Etki" metni görünür | Yüksek |
| DET-06 | Viewer | Haber kartını genişlet/daralt | İlk haber varsayılan açık; diğerleri collapse/expand | Yüksek |
| DET-07 | Viewer | "Kaynağa git ↗" linkine tıkla | Kaynak URL yeni sekmede açılır | Yüksek |
| DET-08 | Viewer | "★ Yıldız'ı nasıl etkiler?" butonuna tıkla | "Analiz ediliyor..." sonra LLM analiz metni; tekrar tıklayınca kapanır/açılır (yeniden çağrı yok) | Yüksek |
| DET-09 | Viewer | Sağ alttaki chatbot FAB'a tıkla | `/chatbot` sayfasına gider (isteğe bağlı `digest_id` parametresi) | Orta |
| DET-10 | Viewer | "← Bültenler" ve alt navigasyon (önceki/sonraki) | Doğru bültenler arası geçiş | Orta |
| DET-11 | Viewer | Var olmayan digest ID ile URL dene | 404 veya hata ekranı | Orta |
| DET-12 | Viewer | Detay açıldığında okundu durumu | Bülten otomatik veya ReadToggle ile okundu işaretlenebilir (ürün davranışına göre) | Orta |

### S-CHATBOT — AI Chatbot (`/chatbot`)

| ID | Rol | Adımlar | Beklenen sonuç | Öncelik |
|----|-----|--------|----------------|---------|
| CHAT-01 | Viewer | Chatbot sayfasını aç | Karşılama ekranı: örnek soru chip'leri | Kritik |
| CHAT-02 | Viewer | Örnek chip'lerden birine tıkla | Soru gönderilir; kullanıcı baloncuğu sağda görünür | Yüksek |
| CHAT-03 | Viewer | Manuel soru yaz, gönder | Typing animasyonu; ardından AI yanıtı solda; kaynak referansları (varsa) listelenir | Kritik |
| CHAT-04 | Viewer | Yanıt beklerken ikinci soru göndermeyi dene | Input ve gönder devre dışı | Yüksek |
| CHAT-05 | Viewer | Ana sayfadan `?q=...` ile gel | Soru otomatik gönderilir | Yüksek |
| CHAT-06 | Viewer | Bülten detayından `?digest_id=...` ile gel (varsa) | Bülten bağlamı bilgi mesajı | Orta |
| CHAT-07 | Viewer | Kaynak linkine tıkla | Dış kaynak yeni sekmede açılır | Orta |
| CHAT-08 | Viewer | LLM hata senaryosu (API key yok / tüm provider down) | Kırmızı hata metni veya "Yanıt üretilemedi" + tekrar dene | Yüksek |
| CHAT-09 | Admin | Viewer ile aynı CHAT-01–08 | Yanıt altında token bilgisi admin'e görünebilir | Düşük |

---

## 7. Admin — Kullanıcı ve kaynak yönetimi

### S-ADMIN-USERS — Kullanıcılar (`/admin/users`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| ADM-U-01 | Sayfayı aç | Kullanıcı tablosu: ad, e-posta, rol, durum, son giriş | Kritik |
| ADM-U-02 | Rol ve durum filtrelerini uygula | Tablo filtrelenir | Orta |
| ADM-U-03 | Arama kutusuna isim/e-posta yaz | Debounced arama sonuçları güncellenir | Orta |
| ADM-U-04 | "Kullanıcı Oluştur" → formu doldur, kaydet | Toast başarı; yeni kullanıcı tabloda | Kritik |
| ADM-U-05 | Aynı e-posta ile ikinci kullanıcı oluştur | "Bu e-posta adresi zaten kullanılıyor." | Yüksek |
| ADM-U-06 | Zayıf şifre ile oluşturmayı dene | Politika kuralları karşılanmadan kayıt olmaz | Yüksek |
| ADM-U-07 | Mevcut kullanıcıyı düzenle (ad, rol) | Değişiklikler kaydedilir; e-posta alanı değiştirilemez | Yüksek |
| ADM-U-08 | Kullanıcıyı pasif yap (onay diyaloğu) | Durum "Pasif"; o kullanıcı ile giriş 401/hesap pasif mesajı | Kritik |
| ADM-U-09 | Pasif kullanıcıyı tekrar aktif et | Giriş tekrar çalışır | Yüksek |
| ADM-U-10 | Kendi admin hesabında "Pasif Yap" seçeneği | Menüde görünmez veya engellenir | Kritik |
| ADM-U-11 | Denetim kayıtlarında USER_CREATED / USER_UPDATED | İlgili olaylar listelenir | Orta |

### S-ADMIN-SOURCES — Kaynaklar (`/admin/sources`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| ADM-S-01 | Sayfayı aç | Kaynak tablosu: ad, tip, kategori, durum toggle, sağlık noktası | Kritik |
| ADM-S-02 | Tip ve durum filtreleri | Liste güncellenir | Orta |
| ADM-S-03 | "Kaynak Ekle" → RSS formu doldur | Kayıt oluşur; ilk bağlantı uyarısı (başarısız URL) toast ile bildirilebilir | Kritik |
| ADM-S-04 | E-posta veya Gov tipi kaynak ekle | Tipine özel alanlar görünür ve kayıt olur | Yüksek |
| ADM-S-05 | Aktif/pasif toggle | Anında güncellenir; hata olursa geri alınır | Yüksek |
| ADM-S-06 | Kaynağı düzenle | Değişiklikler kaydedilir | Yüksek |
| ADM-S-07 | Kaynak sil (onay) | ConfirmDialog; silme sonrası listeden kalkar | Yüksek |
| ADM-S-08 | Sağlık noktasına hover | Son 24 saat istatistik tooltip'i | Düşük |

---

## 8. Admin — AI ve içerik yönetimi

### S-ADMIN-PROMPTS — Prompt şablonları (`/admin/prompt-templates`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| ADM-P-01 | Sayfayı aç | Şablon listesi: ad, digest tipi, durum, versiyon | Kritik |
| ADM-P-02 | Yeni şablon oluştur | Kayıt listeye eklenir | Yüksek |
| ADM-P-03 | Şablonu düzenle (system/user prompt) | Yeni versiyon oluşur | Yüksek |
| ADM-P-04 | Pasif şablonu "Aktif Yap" (onay) | Aynı tipteki önceki aktif şablon pasifleşir | Kritik |
| ADM-P-05 | "Test Et" ile şablon dene | Test panelinde LLM çıktısı ve token kullanımı görünür | Yüksek |
| ADM-P-06 | Versiyon geçmişini incele | Eski versiyon readonly görüntülenir | Orta |

### S-ADMIN-API-KEYS — API anahtarları (`/admin/api-keys`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| ADM-K-01 | Sayfayı aç | Provider kartları; maskelenmiş key (son 4 karakter) | Kritik |
| ADM-K-02 | Yeni API key ekle (geçerli) | Kart listeye eklenir; doğrulama başarılı | Kritik |
| ADM-K-03 | Geçersiz key ekle | Uyarı toast; key yine de kayıtlı olabilir | Orta |
| ADM-K-04 | Key aktif/pasif toggle | Durum güncellenir | Yüksek |
| ADM-K-05 | Kullanım grafiği ve fonksiyon kırılımı | Son 7/30 gün verisi görüntülenir | Orta |
| ADM-K-06 | Key sil (onay) | Kart kaldırılır | Yüksek |
| ADM-K-07 | Tüm key'ler pasifken chatbot dene | Kullanıcıya anlamlı hata mesajı | Yüksek |

### S-ADMIN-CHAT-HISTORY — Sohbet geçmişi (`/admin/chat-history`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| ADM-CH-01 | Viewer ile chatbot'ta soru sor, admin olarak geçmişi aç | Yeni kayıt tabloda | Kritik |
| ADM-CH-02 | Kullanıcı ve tarih filtresi uygula | Liste filtrelenir | Orta |
| ADM-CH-03 | "Detay" modalını aç | Soru, yanıt, kaynaklar, token bilgisi | Yüksek |
| ADM-CH-04 | Arama kutusuna soru metni yaz | Eşleşen kayıtlar | Orta |

---

## 9. Admin — Sistem yönetimi

### S-ADMIN-NOTIFICATIONS — Bildirimler (`/admin/notifications`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| ADM-N-01 | Sayfayı aç | Mail alıcı listesi, bildirim zamanlaması, oturum ayarları kartları | Kritik |
| ADM-N-02 | Mail alıcısı ekle (mevcut kullanıcıdan) | Alıcı tabloda; aynı kullanıcı tekrar eklenemez | Yüksek |
| ADM-N-03 | Alıcı bildirim tipi toggle / kaldır | Değişiklik kaydedilir | Orta |
| ADM-N-04 | Digest bildirim gün/saat değiştir, kaydet | Ayarlar persist edilir | Yüksek |
| ADM-N-05 | JWT access/refresh sürelerini değiştir (onay) | Kayıt sonrası yeni oturumlar yeni süreyle | Orta |

### S-ADMIN-AUDIT-LOGS — Denetim kayıtları (`/admin/audit-logs`)

| ID | Adımlar | Beklenen sonuç | Öncelik |
|----|--------|----------------|---------|
| ADM-A-01 | Sayfayı aç | Olay listesi: zaman, tip, kullanıcı, hedef | Kritik |
| ADM-A-02 | Login yaptıktan sonra listeyi yenile | USER_LOGIN kaydı görünür | Yüksek |
| ADM-A-03 | Olay tipi ve kullanıcı filtresi | Liste filtrelenir | Orta |
| ADM-A-04 | Satırı genişlet (detay) | JSON payload formatlı görünür; hassas veri (şifre, API key) **yok** | Kritik |
| ADM-A-05 | "Daha fazla yükle" | Eski kayıtlar gelir | Orta |

---

## 10. Uçtan uca senaryolar (smoke)

Bu senaryolar tek oturumda ardışık çalıştırılarak MVP-0 kabulü için önerilir.

### Senaryo A — Viewer günlük kullanım (~10 dk)

| Adım | Eylem | Kontrol |
|------|-------|---------|
| 1 | `viewer1@ygip.test` ile giriş | PillNav görünür |
| 2 | Ana sayfada günün özetini oku | Brief ve istatistikler dolu |
| 3 | Okunmamış bültene git, detayı oku | TOC, bölümler, haber expand |
| 4 | Bir haber için Yıldız etki analizi iste | Analiz metni gelir |
| 5 | Bülteni okundu işaretle | Listede durum güncellenir |
| 6 | Chatbot'ta sektörel soru sor | Yanıt + kaynak |
| 7 | Çıkış yap | Login'e dönüş |

### Senaryo B — Admin operasyon (~20 dk)

| Adım | Eylem | Kontrol |
|------|-------|---------|
| 1 | `admin@ygip.test` ile giriş | Sidebar + yönetim menüsü |
| 2 | Yeni viewer kullanıcı oluştur | Tabloda görünür |
| 3 | Yeni RSS kaynağı ekle | Listede; toggle aktif |
| 4 | Prompt şablonunda "Test Et" çalıştır | Test çıktısı |
| 5 | API key durumunu kontrol et | En az bir aktif provider |
| 6 | Bildirim alıcısı ekle | Alıcı listesinde |
| 7 | Chat geçmişinde viewer sorusunu bul | Detay modal |
| 8 | Denetim logunda son işlemleri doğrula | CREATE/UPDATE olayları |
| 9 | Oluşturulan viewer ile giriş (ayrı tarayıcı/incognito) | Viewer deneyimi çalışır |

### Senaryo C — Güvenlik smoke (~5 dk)

| Adım | Eylem | Kontrol |
|------|-------|---------|
| 1 | Viewer ile `/admin/users` dene | Erişim yok |
| 2 | Pasif kullanıcı ile giriş dene | Hesap pasif mesajı |
| 3 | Admin işlemi sonrası audit log | Olay kaydı var |
| 4 | API key tam değeri ekranda arama | Yalnızca maskelenmiş gösterim |

---

## 11. Mobil uygulama (MVP-0 — Faz 7)

React Native uygulaması hazır olduğunda aşağıdaki maddeler **mobil cihazda** tekrarlanır. Web ile aynı S-* kodları geçerlidir; farklar parantez içinde not edilmiştir.

| ID | Ekran | Adımlar | Beklenen sonuç |
|----|-------|--------|----------------|
| MOB-01 | S-LOGIN | Giriş | Secure storage'da token |
| MOB-02 | S-HOME | Tab: Ana Sayfa | Brief + teaser |
| MOB-03 | S-DIGESTS-LIST | Tab: Bültenler | Kart listesi |
| MOB-04 | S-DIGEST-DETAIL | Kart tıkla | TOC chip'ler; FAB |
| MOB-05 | S-CHATBOT | Tab: Chatbot | KeyboardAvoidingView |
| MOB-06 | Push bildirimi | Yeni digest bildirimi (staging) | Uygulama açılır, ilgili digest |

---

## 12. Bilinen kapsam dışı / NA

| Madde | Not |
|-------|-----|
| E2E otomasyon | MVP-0'da Playwright yok — bu belge manuel kaynak |
| Manuel digest tetikleme (S-DIGEST-TRIGGER-CONFIRM) | Spec'te var; web UI henüz yoksa **NA** |
| Self-servis kayıt | Ürün kapsamı dışı |
| Çoklu dil | Yalnızca Türkçe UI |

---

## 13. Onay imzası

| Rol | Ad | Tarih | Sonuç (Geçti / Kaldı) |
|-----|-----|-------|-------------------------|
| Tester | | | |
| Product / İş birimi | | | |
| Teknik reviewer | | | |

**Kritik madde özeti:** Tüm **Kritik** öncelikli maddeler **G** ise MVP-0 web UI human gate için önerilir. Kalan maddeler release notlarında takip edilir.

---

*Son güncelleme: 2026-06-19 — MVP-0 ekran kataloğu ile uyumlu.*

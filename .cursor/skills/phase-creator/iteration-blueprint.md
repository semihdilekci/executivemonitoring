# İterasyon Blueprint — Uygulama Hazır Plan Şablonu

Bu dosya her faz `.mdc` içindeki **tek bir iterasyonun** zorunlu yapısıdır. Amaç: geliştirici agent'ın **Plan moduna geçmeden** aynı netlikte çalışması; spec `Docs/` içinde kalır, iterasyon **ne yapılacağını** ve **hangi doc bölümünün neden okunacağını** taşır.

**Altın kural:** Spec detayı kopyalanmaz → `Docs/<dosya>` §bölüm + uygulama notu. İterasyon, doc'u okumadan kod yazılamayacak kadar somut olmalı.

---

## Context window disiplini

Her iterasyon **tek chat / tek PR** içinde bitmeli. Aşağıdakilerden biri varsa iterasyonu böl:

| Sinyal | Eylem |
| ------ | ----- |
| 8+ dosya oluştur/güncelle | Alt iterasyona böl |
| 2+ katman (ör. API + FE) aynı iterasyonda | Katman başına iterasyon (istisna: net dikey dilim ve ≤6 dosya) |
| 4+ farklı `Docs/` dosyasından bağımsız domain | Böl veya docs güncellemesini önceki iterasyona al |
| Integration + unit + migration + IaC aynı anda | En fazla 2 tür iş bir iterasyonda |
| Stop checklist 10+ madde | İşi küçült |

**Hedef boyut:** 3–8 uygulama adımı; 4–12 dosya; agent yalnızca **Docs okuma sırası**ndaki bölümleri okur — tüm spec değil.

---

## Zorunlu iterasyon iskeleti

Her iterasyon aşağıdaki bölümlerin **tamamını** içerir. Eksik bölüm = iterasyon tamamlanmamış sayılır.

````markdown
### İterasyon N — <2–5 kelime özet>

**Hedef:** <ölçülebilir tek cümle — merge sonrası ne değişmiş olacak>

**Teslim çıktısı:**
- <somut artefakt: dosya, endpoint, migration, workflow, test suite>

**Önkoşullar:**
- [ ] İterasyon N-1 Stop tamam
- [ ] <DB migration, env, branch vb.>

**Docs okuma sırası:** (yalnızca bunları oku — sırayla)
1. `Docs/10_IMPLEMENTATION_ROADMAP.md` §<N.M> — iterasyon kapsamı
2. `Docs/03_API_CONTRACTS.md` §<x> — <neden: request/response/error>
3. `Docs/07_SECURITY_IMPLEMENTATION.md` §<y> — <neden: guard, audit, rate limit>
4. …

**Uygulama planı:**
1. <İlk adım — hangi dosyada ne pattern>
2. <İkinci adım — bağımlılık sırası>
3. …
4. Test ve doğrulama adımı

**Dosya kapsamı:**

| İşlem | Path |
| ----- | ---- |
| Oluştur | `apps/api/...` |
| Güncelle | `packages/shared/...` |
| Dokunma | `…` (sonraki iterasyon / başka faz) |

**Spec → kod eşlemesi:**

| Gereksinim | Docs referansı | Uygulama notu |
| ---------- | -------------- | ------------- |
| Login 401 pasif kullanıcı | `Docs/03` §2.1 | `is_active=false` → `UNAUTHORIZED` |
| Audit aynı transaction | `Docs/07` §9 | `AuditService` commit öncesi |
| … | … | … |

**Kalite kapıları:** (`Docs/08_TESTING_STRATEGY.md` + ilgili glob rule)
- [ ] Pozitif senaryo testi
- [ ] En az bir deny testi (RBAC / validation / parse hatası)
- [ ] `ruff` + `mypy` + ilgili `pytest` yeşil
- [ ] Coverage: <modül> ≥<% hedef from 04-quality-gates>

**Bu iterasyonda yok:**
- <scope creep önleme — özellikle sonraki iterasyon / faz>

**Risk / dikkat:**
- <bilinen edge case, sık yapılan hata, doc-kod boşluğu uyarısı>

**Stop:**
- [ ] <komut veya smoke adımı>
- [ ] <test komutu>
- [ ] PR/onay → İterasyon N+1
````

Son iterasyonda Stop son satırı: `Faz N Done Definition; roadmap işareti.`

---

## Docs referans formatı

Tutarlı ve tıklanabilir:

```
`Docs/<DOSYA>.md` §<numara veya başlık> — <1 cümle: bu iterasyonda neden okunur>
```

Örnekler:
- `` `Docs/03_API_CONTRACTS.md` §2 Auth — login/refresh/logout contract ve error code'lar ``
- `` `Docs/06_SCREEN_CATALOG.md` — S-USER-LIST, S-USER-EDIT (permission + form state) ``
- `` `Docs/02_DATABASE_SCHEMA.md` — users tablosu, index ve FK isimleri ``

**Yasak:** `docs/03'ü oku`, `API spec`, `backend spec` (path/bölüm yok).

**Zorunlu:** Her uygulama planı maddesi en az bir Docs referansına bağlanır veya "mevcut pattern" için `` `Docs/04` §X `` gösterilir.

---

## Uygulama planı yazım kuralları

Plan modu kalitesi için her madde:

1. **Fiil + nesne + konum** — "Auth router'da `POST /auth/login` ekle (`apps/api/routers/auth.py`)"
2. **Pattern kaynağı** — "Mevcut `users` router guard pattern'i (`Docs/04` §5)"
3. **Sıra** — migration → model → service → router → test
4. **Doğrulama gömülü** — son maddeler test komutu içerir

**İyi madde:** `AuditService.log_event` — state-changing işlemlerde aynı DB session (`Docs/07` §9); önce `tests/unit/test_audit_service.py` mock.

**Kötü madde:** `Auth'u implement et.`

---

## Spec → kod eşlemesi tablosu

Docs'taki her kritik gereksinim için bir satır. Kopyalama değil — **pointer + uygulama kararı**.

| Ne zaman satır ekle | Örnek |
| ------------------- | ----- |
| Endpoint | Method, path, RBAC, error code |
| Ekran | `S-*` ID, route, permission |
| Tablo/migration | Tablo adı, enum, index |
| Güvenlik | Rate limit, audit event_type, secret handling |
| Test | Deny senaryosu, coverage hedefi |

Boş tablo yalnızca saf scaffold/CI iterasyonlarında kabul edilir; o durumda **Kalite kapıları** yine dolu olmalı.

---

## Tam örnek (kısaltılmış — Auth endpoints)

```markdown
### İterasyon 3 — Auth Endpoints (1.3)

**Hedef:** `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` çalışır; integration test login→refresh→logout yeşil.

**Teslim çıktısı:**
- `apps/api/routers/auth.py` + Pydantic şemalar
- `tests/integration/test_auth_flow.py`
- Audit: başarılı login → `USER_LOGIN`

**Önkoşullar:**
- [ ] İterasyon 2 Stop (JWT + bcrypt unit testleri yeşil)
- [ ] `users` tablosu migration uygulanmış

**Docs okuma sırası:**
1. `Docs/10_IMPLEMENTATION_ROADMAP.md` §1.3 — kapsam ve Stop
2. `Docs/03_API_CONTRACTS.md` §2 — request/response, cookie/header, error code
3. `Docs/07_SECURITY_IMPLEMENTATION.md` §3 — JWT süreleri; §2 — rate limit auth endpoint
4. `Docs/04_BACKEND_SPEC.md` §5 — router + `Depends(get_current_user)` kalıbı
5. `Docs/08_TESTING_STRATEGY.md` — auth integration test beklentisi

**Uygulama planı:**
1. `schemas/auth.py` — `LoginRequest`, `TokenResponse`; `Docs/03` §2 alanları birebir
2. `services/auth_service.py` — credential verify, token pair üret; pasif kullanıcı 401
3. `routers/auth.py` — üç endpoint; logout refresh invalidate
4. Rate limit dependency auth router'a (`Docs/07` §2)
5. Login success → `audit_logs` aynı transaction (`Docs/07` §9)
6. `tests/integration/test_auth_flow.py` — pozitif akış + wrong password + inactive user deny

**Dosya kapsamı:**

| İşlem | Path |
| ----- | ---- |
| Oluştur | `apps/api/routers/auth.py`, `apps/api/schemas/auth.py`, `apps/api/services/auth_service.py`, `tests/integration/test_auth_flow.py` |
| Güncelle | `apps/api/main.py` (router include) |
| Dokunma | User CRUD (İterasyon 4), password reset (İterasyon 7) |

**Spec → kod eşlemesi:**

| Gereksinim | Docs referansı | Uygulama notu |
| ---------- | -------------- | ------------- |
| Login body email+password | `Docs/03` §2.1 | Pydantic `EmailStr` |
| Hatalı şifre | `Docs/03` §2.1 | `UNAUTHORIZED`, bilgi sızıntısı yok |
| Refresh rotation | `Docs/03` §2.2 | Eski refresh geçersiz |
| Auth rate limit | `Docs/07` §2 | 10 req/dk/IP |

**Kalite kapıları:**
- [ ] Integration: login→refresh→logout
- [ ] Deny: inactive user, bad password
- [ ] `pytest tests/integration/test_auth_flow.py` yeşil
- [ ] Auth modülü coverage ≥%90 (`04-quality-gates`)

**Bu iterasyonda yok:** User CRUD, password reset, frontend cookie wiring

**Risk / dikkat:** `password_hash` response veya log'a sızmamalı (`Docs/07` §3)

**Stop:**
- [ ] `pytest tests/integration/test_auth_flow.py -v`
- [ ] `ruff check apps/api` + `mypy apps/api`
- [ ] PR/onay → İterasyon 4
```

---

## İterasyon bölme karar ağacı

```
Faz kapsamı net mi?
├─ Hayır → önce docs/10 güncelle, sonra iterasyonları yaz
└─ Evet → katman sırası: altyapı → domain → API → UI → E2E
    └─ Her katman için:
        ├─ Tek sorumluluk (1 bounded context)
        ├─ Dosya kapsamı ≤12
        └─ Docs okuma ≤5 dosya, her biri belirli §
            └─ Aşılıyorsa → İterasyon N.a / N.b veya N+1
```

---

## phase-creator doğrulama (iterasyon başına)

- [ ] 9 zorunlu bölüm dolu (Hedef … Stop)
- [ ] Docs okuma sırası ≤5 dosya; her satırda § veya `S-*`
- [ ] Uygulama planı ≥3 somut adım
- [ ] Spec → kod tablosu ≥3 satır (veya scaffold istisnası belgelenmiş)
- [ ] Dosya kapsamı "Dokunma" dolu
- [ ] Stop'ta çalıştırılabilir komut var
- [ ] Plan moduna tekrar ihtiyaç bırakmıyor — agent doğrudan koda geçebilir

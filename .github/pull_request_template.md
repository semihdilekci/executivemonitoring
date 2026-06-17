## Özet

<!-- Hangi iterasyon: MVP-0 / Faz N / N.M -->

- 

## Test durumu

- [ ] `ruff check .` geçiyor
- [ ] `mypy apps/ services/ packages/` geçiyor
- [ ] `pytest tests/ -v` geçiyor

## Kontrol listesi

Tam liste: [Docs/09_DEV_WORKFLOW.md §4.2](../Docs/09_DEV_WORKFLOW.md)

- [ ] Tüm testler local'de geçiyor (`pytest tests/ -v`)
- [ ] Lint hatası yok (`ruff check .`)
- [ ] Type check hatası yok (`mypy apps/ services/ packages/`)
- [ ] Yeni env var varsa `.env.example` güncellendi
- [ ] Yeni DB tablosu varsa migration dosyası oluşturuldu
- [ ] Yeni API endpoint varsa OpenAPI şeması doğru üretiliyor
- [ ] Yeni collector varsa `BaseCollector` implement edildi

## Migration / env

| Soru | Cevap |
|------|-------|
| Migration var mı? | evet / hayır |
| Yeni env var var mı? | evet / hayır |

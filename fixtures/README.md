# Geliştirme ve test için sentetik veri dosyaları burada tutulur.

Production verisi bu dizine **taşınmaz** (`Docs/09_DEV_WORKFLOW.md`).

## Yükleme

```bash
alembic upgrade head
python scripts/seed.py
```

Tüm dev kullanıcıları için varsayılan şifre: `DevPass1` (yalnızca local geliştirme).

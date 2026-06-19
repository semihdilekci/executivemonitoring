"""env_loader unit testleri."""

from __future__ import annotations

import pytest
from packages.shared import env_loader


def test_get_database_url_prefers_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/from_env")
    assert env_loader.get_database_url() == "postgresql+asyncpg://user:pass@localhost:5432/from_env"


def test_get_database_url_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(env_loader, "load_dotenv_file", lambda **_: False)
    with pytest.raises(RuntimeError, match="DATABASE_URL bulunamadı"):
        env_loader.get_database_url(required=True)


def test_safe_database_target_hides_credentials() -> None:
    url = "postgresql+asyncpg://secret:secret@db.example.com:5432/mydb"
    assert env_loader.safe_database_target(url) == "db.example.com:5432/mydb"


def test_async_to_sync_database_url() -> None:
    url = "postgresql+asyncpg://u:p@localhost/db"
    assert env_loader.async_to_sync_database_url(url) == "postgresql+psycopg2://u:p@localhost/db"

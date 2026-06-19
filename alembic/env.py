"""Alembic migration environment."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from packages.shared.env_loader import (
    async_to_sync_database_url,
    get_database_url,
    load_dotenv_file,
)
from packages.shared.models import Base
from sqlalchemy import engine_from_config, pool

# Alembic Config object — alembic.ini değerleri
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    """asyncpg URL'ini Alembic için psycopg2 sync URL'ine çevirir."""
    load_dotenv_file(override=False)
    url = get_database_url(required=True)
    return async_to_sync_database_url(url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

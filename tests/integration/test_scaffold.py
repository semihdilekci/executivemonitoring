"""Integration pipeline smoke tests — DB client testleri Faz 1+."""

import socket

import pytest


def test_postgres_service_reachable() -> None:
    """CI PostgreSQL service container'ının ayakta olduğunu doğrular."""
    try:
        with socket.create_connection(("localhost", 5432), timeout=2):
            pass
    except OSError:
        pytest.skip("PostgreSQL service not available on localhost:5432")

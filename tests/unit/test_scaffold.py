"""Monorepo scaffold smoke tests."""


def test_scaffold_imports() -> None:
    """Verify core Python packages are importable."""
    import apps  # noqa: F401
    import packages  # noqa: F401
    import services  # noqa: F401

    assert True

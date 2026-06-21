"""Lambda bundle script smoke testleri (`scripts/build_lambda.sh`, Faz 8.2).

`BUNDLE_SKIP_DEPS=1` ile çalıştırılır — pip vendoring atlanır, offline + hızlı.
Artifact içeriği (handler import path + monorepo paketleri) doğrulanır.
"""

from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_lambda.sh"

# target → (zip içindeki handler dosyası, CDK handler import string)
TARGETS = {
    "collector": (
        "services/collectors/handler.py",
        "services.collectors.handler.lambda_handler",
    ),
    "processor": (
        "services/processor/handlers/processor_handler.py",
        "services.processor.handlers.processor_handler.lambda_handler",
    ),
}


def _run_bundle(target: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "BUNDLE_SKIP_DEPS": "1"}
    return subprocess.run(
        ["bash", str(BUILD_SCRIPT), target],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module", params=sorted(TARGETS))
def bundle_zip(request: pytest.FixtureRequest) -> tuple[str, Path]:
    target = request.param
    result = _run_bundle(target)
    assert result.returncode == 0, f"bundle script başarısız:\n{result.stderr}"
    zip_path = REPO_ROOT / "dist" / "lambda" / f"{target}.zip"
    assert zip_path.exists(), f"artifact üretilmedi: {zip_path}"
    return target, zip_path


def test_bundle_contains_handler_module(bundle_zip: tuple[str, Path]) -> None:
    """Handler dosyası zip içinde root-relative import path ile bulunur."""
    target, zip_path = bundle_zip
    handler_file, _ = TARGETS[target]
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert handler_file in names, f"{handler_file} artifact'ta yok"


def test_bundle_contains_shared_package(bundle_zip: tuple[str, Path]) -> None:
    """packages/shared root'ta — handler'lar `from packages.shared...` import eder."""
    _, zip_path = bundle_zip
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert any(n.startswith("packages/shared/") for n in names), "packages/shared eksik"
    assert "packages/__init__.py" in names, "packages namespace __init__ eksik"


def test_bundle_excludes_pycache(bundle_zip: tuple[str, Path]) -> None:
    """__pycache__ / .pyc artefaktları bundle'a sızmamalı (boyut + tekrarlanabilirlik)."""
    _, zip_path = bundle_zip
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert not any("__pycache__" in n for n in names), "__pycache__ bundle'a sızdı"
    assert not any(n.endswith(".pyc") for n in names), ".pyc bundle'a sızdı"


def test_invalid_target_exits_nonzero() -> None:
    """Tanımsız hedef → exit kodu != 0, artifact üretmez."""
    result = _run_bundle("invalid-target")
    assert result.returncode != 0

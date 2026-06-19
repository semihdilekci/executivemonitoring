"""Kök pytest yapılandırması — `.env` erken yükleme."""

from __future__ import annotations

from packages.shared.env_loader import load_dotenv_file

# Integration/unit testler ve fixture'lar önce `.env` okusun.
load_dotenv_file(override=False)

"""Lambda deploy stub — synth/IaC için minimal giriş noktası.

Gerçek deploy'da monorepo paketi bundle edilir (`infra/README.md`).
"""

from __future__ import annotations

from typing import Any


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Collector Lambda giriş — deploy artifact ile services.collectors.handler'a yönlendirilir."""
    return {
        "statusCode": 501,
        "body": {
            "message": "Collector paketi deploy edilmedi — bundle script kullanın",
            "source_type": event.get("source_type"),
        },
    }

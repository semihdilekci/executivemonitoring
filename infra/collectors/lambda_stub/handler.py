"""Lambda synth placeholder — bundle artifact yokken CDK synth'in geçmesi için.

CDK `Code.from_asset` bundle dizinini (`dist/lambda/collector/`) tercih eder;
yalnızca bundle build edilmediğinde (CI synth) bu stub'a düşer. Gerçek deploy
öncesi `./scripts/build_lambda.sh collector` zorunlu (`infra/README.md`).
Bu stub'a düşen bir deploy 501 döner — handler `services.collectors.handler`
bundle olmadan bulunamaz.
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

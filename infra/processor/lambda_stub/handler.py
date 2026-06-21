"""Lambda synth placeholder — bundle artifact yokken CDK synth'in geçmesi için.

CDK `Code.from_asset` bundle dizinini (`dist/lambda/processor/`) tercih eder;
yalnızca bundle build edilmediğinde (CI synth) bu stub'a düşer. Gerçek deploy
öncesi `./scripts/build_lambda.sh processor` zorunlu (`infra/README.md`).

Bu stub'a düşen bir invoke mesajı işleyemez — bundle olmadan
`services.processor.handlers.processor_handler` bulunamaz. Mesaj kaybını
önlemek için batch'teki tüm kayıtları `batchItemFailures` ile başarısız
raporlar; SQS redrive policy 3 deneme sonrası DLQ'ya taşır (`Docs/04` §8.7).
"""

from __future__ import annotations

from typing import Any


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    """Processor Lambda giriş — deploy artifact ile gerçek handler'a yönlendirilir."""
    del context
    records = event.get("Records", [])
    batch_item_failures: list[dict[str, str]] = []
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict):
                message_id = record.get("messageId")
                if isinstance(message_id, str):
                    batch_item_failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": batch_item_failures}

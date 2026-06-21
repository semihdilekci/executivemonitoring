#!/usr/bin/env bash
#
# smoke_pipeline_dev.sh — Dev pipeline uçtan uca smoke (Faz 8.5).
#
# Akış: collector Lambda invoke → SQS depth gözlem → processor (SQS-triggered)
#       tüketimi → raw_items / processed_items satır artışı doğrulama.
#
# Kaynaklar (dev, `30-infra-aws`): `dev-ygip-collector-<type>`,
# `dev-ygip-sqs-<type>` (+ `-dlq`), `dev-ygip-processor-<type>`.
#
# Kullanım:
#   ./scripts/smoke_pipeline_dev.sh                       # rss, tam akış
#   ./scripts/smoke_pipeline_dev.sh --source-type gov
#   ./scripts/smoke_pipeline_dev.sh --skip-db            # RDS VPC-internal erişilemez ise
#   ./scripts/smoke_pipeline_dev.sh --dry-run            # AWS yok — yalnızca komutları yazdır
#
# Ortam değişkenleri:
#   AWS_REGION    (varsayılan eu-west-1)
#   DATABASE_URL  (DB doğrulama için; yoksa otomatik --skip-db)
#
# Önkoşul: `deploy-dev.yml` veya manuel `cdk deploy` ile dev stack canlı,
#          `aws` CLI yapılandırılmış. DB kontrolü için `psql` (libpq).
#
# Agent kısıtı (`Docs/09` §6.1): bu script salt-okuma gözlem + collector invoke
# yapar; kaynak silmez, prod kaynağa dokunmaz.
#
set -euo pipefail

SOURCE_TYPE="rss"
DRY_RUN=0
SKIP_DB=0
WAIT_SECONDS=45
AWS_REGION="${AWS_REGION:-eu-west-1}"
PREFIX="dev-ygip"

usage() {
  grep '^#' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-type) SOURCE_TYPE="$2"; shift 2 ;;
    --wait) WAIT_SECONDS="$2"; shift 2 ;;
    --region) AWS_REGION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --skip-db) SKIP_DB=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Bilinmeyen argüman: $1" >&2; usage 2 ;;
  esac
done

case "$SOURCE_TYPE" in
  rss|email|gov) ;;
  *) echo "Hata: --source-type rss|email|gov olmalı (verilen: $SOURCE_TYPE)" >&2; exit 2 ;;
esac

COLLECTOR_FN="${PREFIX}-collector-${SOURCE_TYPE}"
QUEUE_NAME="${PREFIX}-sqs-${SOURCE_TYPE}"
DLQ_NAME="${QUEUE_NAME}-dlq"

# DATABASE_URL yoksa DB doğrulamasını otomatik atla.
if [[ "$SKIP_DB" -eq 0 && -z "${DATABASE_URL:-}" ]]; then
  echo "ℹ DATABASE_URL tanımsız — DB doğrulama atlanıyor (--skip-db)."
  SKIP_DB=1
fi

run() {
  echo "    \$ $*"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return 0
  fi
  "$@"
}

# psql ile tek tam-sayı skaler sorgu (DRY_RUN'da 0 döner).
db_scalar() {
  local sql="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "0"
    return 0
  fi
  # asyncpg DSN'i (postgresql+asyncpg://) psql için temizle.
  local dsn="${DATABASE_URL/+asyncpg/}"
  psql "$dsn" -tA -c "$sql"
}

sqs_url() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "https://sqs.${AWS_REGION}.amazonaws.com/000000000000/$1"
    return 0
  fi
  aws sqs get-queue-url --region "$AWS_REGION" --queue-name "$1" --query QueueUrl --output text
}

sqs_depth() {
  local url="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then echo "0"; return 0; fi
  aws sqs get-queue-attributes --region "$AWS_REGION" --queue-url "$url" \
    --attribute-names ApproximateNumberOfMessages \
    --query 'Attributes.ApproximateNumberOfMessages' --output text
}

echo "=== YGIP dev pipeline smoke ($SOURCE_TYPE) ==="
echo "    region:    $AWS_REGION"
echo "    collector: $COLLECTOR_FN"
echo "    queue:     $QUEUE_NAME (+ $DLQ_NAME)"
[[ "$DRY_RUN" -eq 1 ]] && echo "    MOD: DRY-RUN (gerçek AWS çağrısı yok)"
echo

# 0) Baseline DB satır sayıları (artış doğrulaması için).
RAW_BEFORE=0; PROC_BEFORE=0
if [[ "$SKIP_DB" -eq 0 ]]; then
  echo "==> 0) Baseline DB satırları"
  RAW_BEFORE=$(db_scalar "SELECT count(*) FROM raw_items;")
  PROC_BEFORE=$(db_scalar "SELECT count(*) FROM processed_items;")
  echo "    raw_items=$RAW_BEFORE processed_items=$PROC_BEFORE"
fi

# 1) Collector Lambda invoke (EventBridge payload taklidi).
echo "==> 1) Collector invoke: $COLLECTOR_FN"
run aws lambda invoke \
  --region "$AWS_REGION" \
  --function-name "$COLLECTOR_FN" \
  --cli-binary-format raw-in-base64-out \
  --payload "{\"source_type\":\"${SOURCE_TYPE}\"}" \
  /tmp/ygip-collector-out.json
if [[ "$DRY_RUN" -eq 0 ]]; then
  echo "    yanıt: $(cat /tmp/ygip-collector-out.json)"
fi

# 2) SQS depth gözlem (processor tüketmeden önce mesaj görünebilir).
echo "==> 2) SQS depth (invoke sonrası)"
QUEUE_URL=$(sqs_url "$QUEUE_NAME")
DLQ_URL=$(sqs_url "$DLQ_NAME")
echo "    $QUEUE_NAME depth=$(sqs_depth "$QUEUE_URL")"

# 3) Processor (SQS-triggered) tüketimi için bekle.
echo "==> 3) Processor tüketimi bekleniyor (${WAIT_SECONDS}s)"
if [[ "$DRY_RUN" -eq 0 ]]; then
  sleep "$WAIT_SECONDS"
fi

# 4) DLQ kontrolü — mesaj DLQ'ya düştüyse pipeline başarısız.
echo "==> 4) DLQ kontrolü: $DLQ_NAME"
DLQ_DEPTH=$(sqs_depth "$DLQ_URL")
echo "    $DLQ_NAME depth=$DLQ_DEPTH"
if [[ "$DRY_RUN" -eq 0 && "$DLQ_DEPTH" != "0" ]]; then
  echo "✗ SMOKE BAŞARISIZ — $DLQ_DEPTH mesaj DLQ'da (processor hata)." >&2
  exit 1
fi

# 5) DB satır artışı doğrulama.
if [[ "$SKIP_DB" -eq 0 ]]; then
  echo "==> 5) DB satır artışı"
  RAW_AFTER=$(db_scalar "SELECT count(*) FROM raw_items;")
  PROC_AFTER=$(db_scalar "SELECT count(*) FROM processed_items;")
  echo "    raw_items:       $RAW_BEFORE → $RAW_AFTER"
  echo "    processed_items: $PROC_BEFORE → $PROC_AFTER"
  if [[ "$RAW_AFTER" -le "$RAW_BEFORE" ]]; then
    echo "✗ SMOKE BAŞARISIZ — raw_items artmadı (collect/ingest çalışmadı)." >&2
    exit 1
  fi
  if [[ "$PROC_AFTER" -le "$PROC_BEFORE" ]]; then
    echo "✗ SMOKE BAŞARISIZ — processed_items artmadı (processor çalışmadı)." >&2
    exit 1
  fi
else
  echo "==> 5) DB doğrulama atlandı (--skip-db / VPC-internal RDS)."
  echo "    Manuel kontrol: bastion/SSM tüneli ile psql veya admin API."
fi

echo
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "✓ DRY-RUN tamam — komut akışı doğrulandı (gerçek AWS çağrısı yapılmadı)."
else
  echo "✓ SMOKE BAŞARILI — collector → SQS → processor akışı doğrulandı."
fi

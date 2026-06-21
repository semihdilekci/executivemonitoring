#!/usr/bin/env bash
#
# build_lambda.sh — Monorepo paketini Lambda deploy artifact'ına bundle eder.
#
# Kullanım:
#   ./scripts/build_lambda.sh collector
#   ./scripts/build_lambda.sh processor
#
# Çıktı:
#   dist/lambda/<target>/        → staging dizini (services/ + packages/ + vendored deps)
#   dist/lambda/<target>.zip     → deploy artifact (CDK Code.from_asset, İter 3–4)
#
# Handler giriş noktaları (CDK `handler` parametresi):
#   collector → services.collectors.handler.lambda_handler
#   processor → services.processor.handlers.processor_handler.lambda_handler
#
# Ortam değişkenleri:
#   BUNDLE_SKIP_DEPS=1      → pip vendoring atlanır (offline test / hızlı smoke)
#   LAMBDA_TARGET_PLATFORM  → set ise manylinux2014_x86_64 cross-compile (macOS → Lambda linux)
#
# Lambda runtime env (deploy-time CDK enjekte eder, `Docs/09` §7):
#   DATABASE_URL, REDIS_URL, SQS_QUEUE_{RSS,EMAIL,GOV,API}_URL, S3_ARCHIVE_BUCKET,
#   AWS_REGION, ENCRYPTION_KEY, OPENAI_API_KEY (processor embedding)
#
set -euo pipefail

TARGET="${1:-}"
if [[ "${TARGET}" != "collector" && "${TARGET}" != "processor" ]]; then
  echo "Hata: hedef 'collector' veya 'processor' olmalı (verilen: '${TARGET:-<boş>}')" >&2
  echo "Kullanım: ./scripts/build_lambda.sh {collector|processor}" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist/lambda"
STAGE_DIR="${DIST_DIR}/${TARGET}"
ZIP_PATH="${DIST_DIR}/${TARGET}.zip"

# Lambda artifact'ta gereksiz API/dev bağımlılıkları hariç tut (boyut 250 MB limit).
EXCLUDE_DEPS_PATTERN='^(fastapi|uvicorn|alembic)\b'

echo "==> Lambda bundle: ${TARGET}"
echo "    repo:  ${REPO_ROOT}"
echo "    stage: ${STAGE_DIR}"

rm -rf "${STAGE_DIR}" "${ZIP_PATH}"
mkdir -p "${STAGE_DIR}"

# 1) Monorepo kaynak paketleri — services/ + packages/ (handler import path'leri root'tan).
echo "==> Kaynak paketleri kopyalanıyor (services/, packages/)"
copy_pkg() {
  local src="$1" dst="$2"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '.mypy_cache' \
      --exclude '.pytest_cache' \
      "${src}/" "${dst}/"
  else
    cp -R "${src}/" "${dst}/"
    find "${dst}" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
    find "${dst}" -type f -name '*.pyc' -delete 2>/dev/null || true
  fi
}
mkdir -p "${STAGE_DIR}/services" "${STAGE_DIR}/packages"
copy_pkg "${REPO_ROOT}/services" "${STAGE_DIR}/services"
copy_pkg "${REPO_ROOT}/packages" "${STAGE_DIR}/packages"

# 2) Runtime bağımlılıkları vendor et (pip install -t).
if [[ "${BUNDLE_SKIP_DEPS:-0}" == "1" ]]; then
  echo "==> BUNDLE_SKIP_DEPS=1 — bağımlılık vendoring atlandı"
else
  echo "==> Bağımlılıklar vendor ediliyor (pip install -t)"
  REQ_FILE="$(mktemp)"
  trap 'rm -f "${REQ_FILE}"' EXIT
  grep -vE "${EXCLUDE_DEPS_PATTERN}" "${REPO_ROOT}/requirements.txt" \
    | grep -vE '^\s*(#|$)' > "${REQ_FILE}"

  PIP_ARGS=(install --no-cache-dir -r "${REQ_FILE}" -t "${STAGE_DIR}")
  if [[ -n "${LAMBDA_TARGET_PLATFORM:-}" ]]; then
    # macOS host → Lambda linux x86_64; manylinux wheel zorunlu (asyncpg, cryptography…).
    PIP_ARGS+=(--platform manylinux2014_x86_64 --python-version 3.12 \
      --implementation cp --only-binary=:all: --upgrade)
  fi
  python3 -m pip "${PIP_ARGS[@]}"

  # Vendored artefakt temizliği — boyut azalt.
  find "${STAGE_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  find "${STAGE_DIR}" -type d -name '*.dist-info' -prune -exec rm -rf {} + 2>/dev/null || true
  find "${STAGE_DIR}" -type d -name 'tests' -path '*/site-packages/*' -prune -exec rm -rf {} + 2>/dev/null || true
fi

# 3) Zip artifact üret (deterministik sıra).
echo "==> Zip oluşturuluyor: ${ZIP_PATH}"
( cd "${STAGE_DIR}" && zip -q -r -X "${ZIP_PATH}" . )

BUNDLE_SIZE="$(du -sh "${STAGE_DIR}" | cut -f1)"
echo "==> Tamamlandı: ${ZIP_PATH} (unzipped ${BUNDLE_SIZE})"
echo "    handler: $( [[ "${TARGET}" == "collector" ]] \
  && echo 'services.collectors.handler.lambda_handler' \
  || echo 'services.processor.handlers.processor_handler.lambda_handler' )"

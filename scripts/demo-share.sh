#!/usr/bin/env bash
#
# YGIP — ngrok statik domain ile tek-URL demo paylaşımı.
#
# Web (:3000) ngrok'tan yayınlanır; tarayıcıdan gelen /api/v1/* istekleri
# Next.js rewrite ile yerel FastAPI'ye (:8000) proxy'lenir → TEK link, CORS yok.
# Postgres/Redis ve LLM secret'ları lokalde kalır; hiçbir şey buluta gitmez.
#
# Tek seferlik hazırlık:
#   1) https://dashboard.ngrok.com → ücretsiz hesap
#   2) Settings → Your Authtoken:   ngrok config add-authtoken <TOKEN>
#   3) Domains → "Create Domain" (1 adet ücretsiz statik domain) → kopyala
#
# Çalıştırma:
#   docker compose up -d                      # postgres + redis (henüz ayakta değilse)
#   NGROK_DOMAIN=your-name.ngrok-free.app  scripts/demo-share.sh
#
# Ctrl-C → uvicorn + next + ngrok hepsi birlikte kapanır.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Demo değişkenlerini .env'den oku (yalnızca ortamda set EDİLMEMİŞSE). Tüm
# dosyayı `source` etmeyiz; CORS_ORIGINS=[...] gibi satırlar bash'i kırar.
if [[ -f "${ROOT}/.env" ]]; then
  for key in NGROK_DOMAIN API_PORT WEB_PORT; do
    if [[ -z "${!key:-}" ]]; then
      val="$(grep -E "^${key}=" "${ROOT}/.env" | tail -n1 | cut -d= -f2- | tr -d '\042\047' || true)"
      [[ -n "$val" ]] && export "${key}=${val}"
    fi
  done
fi

: "${NGROK_DOMAIN:?NGROK_DOMAIN gerekli — .env dosyasina ekleyin veya: NGROK_DOMAIN=your-name.ngrok-free.app scripts/demo-share.sh}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
SHARE_URL="https://${NGROK_DOMAIN}"

# --- Python binary'leri: .venv varsa onu kullan ---------------------------
if [[ -x "${ROOT}/.venv/bin/uvicorn" ]]; then
  UVICORN="${ROOT}/.venv/bin/uvicorn"
  ALEMBIC="${ROOT}/.venv/bin/alembic"
else
  UVICORN="uvicorn"
  ALEMBIC="alembic"
fi

# --- Bağımlılık kontrolü ---------------------------------------------------
for bin in ngrok npm "$UVICORN" "$ALEMBIC"; do
  command -v "$bin" >/dev/null 2>&1 \
    || { echo "✗ '$bin' bulunamadı — kurulu ve PATH'te (veya .venv'de) olmalı." >&2; exit 1; }
done

# --- Altyapı uyarısı (zorunlu değil, sadece bilgilendirme) -----------------
if command -v nc >/dev/null 2>&1; then
  nc -z localhost 6379 >/dev/null 2>&1 \
    || echo "⚠ Redis (6379) erişilemiyor — 'docker compose up -d' çalıştırdınız mı?"
fi

echo "→ Alembic migration (alembic upgrade head)"
"$ALEMBIC" upgrade head

# --- Süreç yönetimi: Ctrl-C'de hepsini topla -------------------------------
pids=()
cleanup() {
  echo
  echo "→ Kapatılıyor..."
  for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

# --- FastAPI (yerel pipeline modu; AWS gerektirmez) ------------------------
echo "→ FastAPI başlatılıyor (127.0.0.1:${API_PORT}, PIPELINE_RUNTIME_MODE=local)"
PIPELINE_RUNTIME_MODE=local \
WEB_BASE_URL="${SHARE_URL}" \
PASSWORD_RESET_BASE_URL="${SHARE_URL}/reset-password" \
  "$UVICORN" apps.api.main:app --host 127.0.0.1 --port "${API_PORT}" &
pids+=($!)

# --- Next.js (tek-origin: API'yi kendi üstünden proxy'ler) -----------------
echo "→ Next.js başlatılıyor (:${WEB_PORT}, API tek-origin proxy)"
(
  cd apps/web && \
  NEXT_PUBLIC_API_BASE_URL="/api/v1" \
  API_INTERNAL_BASE_URL="http://localhost:${API_PORT}/api/v1" \
  API_PROXY_TARGET="http://localhost:${API_PORT}" \
  NEXT_PUBLIC_APP_ENV="production" \
    npm run dev -- --port "${WEB_PORT}"
) &
pids+=($!)

# --- ngrok (statik domain, foreground) -------------------------------------
echo
echo "════════════════════════════════════════════════════════════════"
echo "  Paylaşılacak link:  ${SHARE_URL}"
echo "  (IP/ağ değişse de aynı kalır — proses açık olduğu sürece)"
echo "════════════════════════════════════════════════════════════════"
echo
ngrok http "--url=${NGROK_DOMAIN}" "${WEB_PORT}"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
export QUANT_STORAGE_BACKEND="${QUANT_STORAGE_BACKEND:-sqlite}"
export QUANT_SQLITE_PATH="${QUANT_SQLITE_PATH:-data/quant-platform.sqlite3}"
export QUANT_MARKET_DATA_PROVIDER="${QUANT_MARKET_DATA_PROVIDER:-yfinance}"
export QUANT_API_HOST="${QUANT_API_HOST:-0.0.0.0}"
export QUANT_API_PORT="${QUANT_API_PORT:-18080}"

exec uvicorn apps.api_gateway.main:app --host "$QUANT_API_HOST" --port "$QUANT_API_PORT"

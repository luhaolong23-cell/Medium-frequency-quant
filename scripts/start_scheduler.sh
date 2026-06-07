#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
export QUANT_STORAGE_BACKEND="${QUANT_STORAGE_BACKEND:-sqlite}"
export QUANT_SQLITE_PATH="${QUANT_SQLITE_PATH:-data/quant-platform.sqlite3}"
export QUANT_MARKET_DATA_PROVIDER="${QUANT_MARKET_DATA_PROVIDER:-yfinance}"

exec python -m apps.scheduler.main

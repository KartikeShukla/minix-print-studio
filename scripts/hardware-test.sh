#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${MINIX_PYTHON:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${MINIX_PYTHON:-python3}"
fi

export PYTHONPATH="$ROOT_DIR/daemon/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" -m minixd.hardware_test_cli "$@"

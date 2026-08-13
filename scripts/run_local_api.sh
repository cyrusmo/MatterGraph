#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
exec uv run uvicorn mattergraph_api.main:app --host "${MATTERGRAPH_API_HOST:-127.0.0.1}" --port "${MATTERGRAPH_API_PORT:-8001}" --reload

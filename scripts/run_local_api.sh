#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
export MATTERGRAPH_DEMO_DATA="${MATTERGRAPH_DEMO_DATA:-$ROOT/data/demo/materials_sample.jsonl}"
exec uv run uvicorn app.main:app --host "${MATTERGRAPH_API_HOST:-0.0.0.0}" --port "${MATTERGRAPH_API_PORT:-8000}" --reload

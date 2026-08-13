#!/usr/bin/env bash
set -euo pipefail

DEMO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_HOST="${MATTERGRAPH_API_HOST:-127.0.0.1}"
API_PORT="${MATTERGRAPH_API_PORT:-8001}"
WEB_HOST="${MATTERGRAPH_WEB_HOST:-127.0.0.1}"
WEB_PORT="${MATTERGRAPH_WEB_PORT:-5173}"
PYTHON_BIN="${DEMO_ROOT}/.venv/bin/python"
UVICORN_BIN="${DEMO_ROOT}/.venv/bin/uvicorn"
DEMO_TMP="$(mktemp -d "${TMPDIR:-/tmp}/mattergraph-demo.XXXXXX")"
API_PID=""

cleanup() {
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" 2>/dev/null || true
    wait "${API_PID}" 2>/dev/null || true
  fi
  rm -rf "${DEMO_TMP}"
}
trap cleanup EXIT INT TERM

if [[ ! -x "${PYTHON_BIN}" || ! -x "${UVICORN_BIN}" ]]; then
  echo "MatterGraph virtual environment is missing. Run: uv sync --all-packages --group dev" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to run the public web demo." >&2
  exit 1
fi

port_is_free() {
  "${PYTHON_BIN}" -c \
    'import socket, sys; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((sys.argv[1], int(sys.argv[2]))); s.close()' \
    "$1" "$2" >/dev/null 2>&1
}

require_free_port() {
  local label="$1"
  local host="$2"
  local port="$3"
  if ! port_is_free "${host}" "${port}"; then
    echo "${label} port ${host}:${port} is already occupied; no process was stopped." >&2
    echo "Choose another port with MATTERGRAPH_${label}_PORT=<port>." >&2
    if command -v lsof >/dev/null 2>&1; then
      lsof -nP -iTCP:"${port}" -sTCP:LISTEN >&2 || true
    fi
    exit 1
  fi
}

require_free_port API "${API_HOST}" "${API_PORT}"
require_free_port WEB "${WEB_HOST}" "${WEB_PORT}"

cd "${DEMO_ROOT}"
"${UVICORN_BIN}" mattergraph_api.main:app \
  --host "${API_HOST}" \
  --port "${API_PORT}" >"${DEMO_TMP}/api.log" 2>&1 &
API_PID=$!

READY=0
for _attempt in {1..30}; do
  if ! kill -0 "${API_PID}" 2>/dev/null; then
    echo "MatterGraph API exited during preflight:" >&2
    sed -n '1,160p' "${DEMO_TMP}/api.log" >&2
    exit 1
  fi
  if curl --max-time 1 --silent --fail \
    "http://${API_HOST}:${API_PORT}/demo/preflight" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 0.2
done

if [[ "${READY}" != "1" ]]; then
  echo "MatterGraph API did not become ready within six seconds:" >&2
  sed -n '1,160p' "${DEMO_TMP}/api.log" >&2
  exit 1
fi

echo "MatterGraph public demo is ready."
echo "  UI:  http://${WEB_HOST}:${WEB_PORT}/"
echo "  API: http://${API_HOST}:${API_PORT}/docs"
echo "Press Ctrl-C to stop only these demo processes."

cd "${DEMO_ROOT}/apps/web"
VITE_API_PROXY_TARGET="http://${API_HOST}:${API_PORT}" \
  npm run dev -- --host "${WEB_HOST}" --port "${WEB_PORT}"

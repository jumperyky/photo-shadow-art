#!/usr/bin/env bash
# 開発用: Python API (:8000) と Next.js (:3000) をまとめて起動する。
# Ctrl+C で両方止まる。
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d frontend/node_modules ]; then
  echo "frontend/node_modules がありません。先に 'cd frontend && npm install' を実行してください。" >&2
  exit 1
fi

PY=${PYTHON:-python3}

echo "→ API   http://127.0.0.1:8000"
(cd backend && "$PY" -m uvicorn app.main:app --reload --port 8000) &
API_PID=$!

echo "→ UI    http://localhost:3000"
(cd frontend && npm run dev) &
UI_PID=$!

cleanup() {
  echo
  echo "停止中…"
  kill "$API_PID" "$UI_PID" 2>/dev/null || true
  wait "$API_PID" "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait -n "$API_PID" "$UI_PID"

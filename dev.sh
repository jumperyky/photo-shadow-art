#!/usr/bin/env bash
# 開発用: Python API (:8000) と Next.js (:3000) をまとめて起動する。
# Ctrl+C で両方止まる。
#
#   ./dev.sh                      … http://localhost:3000 で起動
#   PORT_UI=3100 ./dev.sh         … ポートを変える
#   PYTHON=/path/to/python ./dev.sh
#   LAN_HOST=192.168.1.42 ./dev.sh … スマホ等、同じLAN内の別端末から使う
#
# 初回は先に ./setup.sh を実行すること。
set -euo pipefail

cd "$(dirname "$0")"
ROOT=$(pwd)

PORT_API=${PORT_API:-8000}
PORT_UI=${PORT_UI:-3000}

fail() { echo "エラー: $1" >&2; exit 1; }

# --- Python の選択: 明示指定 > ./.venv > PATH の python3 -------------------
if [ -n "${PYTHON:-}" ]; then
  PY=$PYTHON
elif [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY=python3
fi
# サブシェルで cd しても効くよう絶対パスに解決しておく
PY=$(command -v "$PY" 2>/dev/null || echo "$PY")
[ -x "$PY" ] || fail "Python が見つかりません ($PY)。先に ./setup.sh を実行してください。"

# --- 事前チェック ----------------------------------------------------------
if ! "$PY" -c "import fastapi, uvicorn, shapely, trimesh, mapbox_earcut" 2>/dev/null; then
  fail "Python の依存が足りません。先に ./setup.sh を実行してください。
       （使用中の Python: $PY）"
fi

[ -d frontend/node_modules ] \
  || fail "frontend/node_modules がありません。先に ./setup.sh を実行してください。"

port_busy() {
  "$PY" - "$1" <<'EOF' 2>/dev/null
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(0)   # 使用中
finally:
    s.close()
sys.exit(1)       # 空いている
EOF
}

port_busy "$PORT_API" \
  && fail "ポート $PORT_API は使用中です。PORT_API=8001 ./dev.sh のように変更してください。"
port_busy "$PORT_UI" \
  && fail "ポート $PORT_UI は使用中です。PORT_UI=3100 ./dev.sh のように変更してください。"

# --- 起動 ------------------------------------------------------------------
echo "→ API   http://127.0.0.1:$PORT_API"
(cd "$ROOT/backend" && exec "$PY" -m uvicorn app.main:app --reload --port "$PORT_API") &
API_PID=$!

echo "→ UI    http://localhost:$PORT_UI"
(cd "$ROOT/frontend" \
   && API_BASE_URL="http://127.0.0.1:$PORT_API" PORT="$PORT_UI" \
      NEXT_ALLOWED_DEV_ORIGINS="${LAN_HOST:-}" exec npm run dev) &
UI_PID=$!

echo
echo "ブラウザで http://localhost:$PORT_UI を開いてください（Ctrl+C で停止）"
if [ -n "${LAN_HOST:-}" ]; then
  echo "LAN内の別端末からは http://$LAN_HOST:$PORT_UI で開けます。"
else
  echo "スマホ等、同じLAN内の別端末から使いたい場合は LAN_HOST=<このPCのIP> ./dev.sh"
  echo "(詳しくは README『他の端末(スマホなど)から使う』を参照)"
fi

# npm は next を、uvicorn は --reload のワーカーを子として抱えるため、
# 直接の子だけ kill すると孫プロセスが残り、次回起動時に
# 「Another next dev server is already running」やポート使用中で失敗する。
kill_tree() {
  local pid=$1
  local child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  trap - EXIT INT TERM
  echo
  echo "停止中…"
  kill_tree "$API_PID"
  kill_tree "$UI_PID"
  wait "$API_PID" "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait -n "$API_PID" "$UI_PID"

#!/usr/bin/env bash
# 初回セットアップ: Python の仮想環境と npm の依存をまとめて用意する。
#   ./setup.sh     … .venv を作って依存をインストール
# 完了後は ./dev.sh で起動できる（.venv は dev.sh が自動で見つける）。
set -euo pipefail

cd "$(dirname "$0")"

PY=${PYTHON:-python3}

echo "==> Python の確認"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "エラー: python3 が見つかりません。Python 3.10 以上を入れてください。" >&2
  exit 1
fi
"$PY" - <<'EOF'
import sys
if sys.version_info < (3, 10):
    sys.exit(f"エラー: Python 3.10 以上が必要です (今: {sys.version.split()[0]})")
print(f"    Python {sys.version.split()[0]}")
EOF

echo "==> 仮想環境 (.venv) を用意"
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
  echo "    .venv を作成しました"
else
  echo "    既存の .venv を使います"
fi

echo "==> Python の依存をインストール（数分かかることがあります）"
./.venv/bin/python -m pip install --upgrade pip --quiet
./.venv/bin/python -m pip install -r backend/requirements.txt --quiet
echo "    完了"

echo "==> Node の確認"
if ! command -v npm >/dev/null 2>&1; then
  echo "エラー: npm が見つかりません。Node.js 20 以上を入れてください。" >&2
  exit 1
fi
node --version | sed 's/^/    Node /'

echo "==> フロントエンドの依存をインストール"
(cd frontend && npm install --no-audit --no-fund --loglevel=error)
echo "    完了"

echo "==> 動作確認"
./.venv/bin/python -c "
import sys; sys.path.insert(0, '.')
import line_art_stl as la
import keychain_stl as kc
art = la.build_artwork('samples/test_face.png', diameter=150, num_lines=24,
                       samples_per_line=64)
print(f'    ジオメトリ生成 OK (線 {art.line_count} 本)')
try:
    la._load_cascades(); print('    顔検出 OK')
except la.FaceDetectionUnavailable as e:
    print(f'    顔検出は利用できません: {e}')
print('    キーホルダー(3Dブーリアン) '
      + ('OK' if kc.boolean_available() else '利用できません: manifold3d 未導入'))
"

echo
echo "セットアップ完了。次のコマンドで起動できます:"
echo "    ./dev.sh"

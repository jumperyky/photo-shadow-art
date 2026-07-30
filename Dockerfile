# NAS等での常時起動を想定したシングルコンテナ構成。
#
# フロントエンド(Next.js)は静的ファイルに書き出し(output: "export")、
# FastAPIから直接配信する。これによりNode.jsのサーバープロセスが不要になり、
# コンテナ1つ・ポート1つ・単一プロセスで完結する
# (README「NASで常時起動する(Docker)」参照)。
#
# ビルド:
#   docker compose up --build -d
# 単体でビルドする場合:
#   docker build -t photo-shadow-art .
#   docker run -p 8000:8000 -v psa-data:/data photo-shadow-art

# ---------------------------------------------------------------- 1. フロント
FROM node:20-slim AS frontend-builder
WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# next.config.mjs がこの変数を見て output: "export" に切り替える。
# ローカル開発(npm run dev)には影響しない。
ENV NEXT_OUTPUT_EXPORT=1
RUN npm run build

# ---------------------------------------------------------------- 2. Python
FROM python:3.11-slim AS runtime
WORKDIR /app

# opencv-python-headless の実行時に必要な共有ライブラリ。
# (「headless」なのでGUI関連は不要だが、libglibへの内部依存は残る)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# コア(CLI/両生成方式)とAPI本体
COPY line_art_stl.py lithophane_stl.py photo_common.py ./
COPY backend/app ./backend/app
# サンプル画像はコード内で生成した合成画像で実在の人物写真ではない(README参照)
COPY samples ./samples

# 静的エクスポートしたフロントエンド。main.py がこのディレクトリの有無を見て
# 自動でマウントする(存在しなければ何もしない=ローカル開発と同じ挙動)。
COPY --from=frontend-builder /src/frontend/out ./frontend/out

# アップロード画像の保存先。TTL(既定6時間)で自動削除されるため、
# 揮発してよいボリューム。永続化したい場合だけ docker-compose でマウントする。
ENV PSA_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

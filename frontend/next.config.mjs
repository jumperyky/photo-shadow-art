/** @type {import('next').NextConfig} */

// バックエンド(FastAPI)のURL。開発時は localhost:8000。
const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:8000";

// LAN内の別端末(スマホ・タブレット等)から開発サーバーを開きたい場合、
// PCのIPをカンマ区切りで指定する(例: NEXT_ALLOWED_DEV_ORIGINS=192.168.1.42)。
// Next.js 16 は既定でこの手のクロスオリジンなdevリクエストを403で拒否するため
// (HMRやJSバンドルの取得が失敗し、画面が真っ白になる)、許可するホストを
// 明示する必要がある。ポートは不要(ホスト名/IPだけ見て判定される)。
// README「他の端末(スマホなど)から使う」を参照。
const allowedDevOrigins = (process.env.NEXT_ALLOWED_DEV_ORIGINS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

// NAS等にDockerで常時起動する構成向け。このアプリは全ページが静的
// (page.tsxは "use client" のみで、サーバー専用APIは使っていない)ので、
// `output: "export"` でビルド結果を静的ファイルに書き出し、FastAPIから
// 直接配信できる。これによりNext.jsのサーバープロセス自体が不要になり、
// コンテナ1つ・ポート1つ・単一プロセスで完結する(README参照)。
//
// ローカル開発 (`./dev.sh` / `npm run dev`) には影響しない。開発時は
// この変数を設定しないので、これまで通りNextのdevサーバー+rewritesの
// プロキシ構成のまま動く。
const STATIC_EXPORT = process.env.NEXT_OUTPUT_EXPORT === "1";

const nextConfig = {
  reactStrictMode: true,
  ...(STATIC_EXPORT ? { output: "export" } : {}),
  ...(allowedDevOrigins.length > 0 ? { allowedDevOrigins } : {}),
  // /api/* をPython APIへプロキシする。フロントからは常に同一オリジンで叩けるので
  // CORSやAPI URLの環境差を気にしなくてよい。
  // 静的エクスポート時は rewrites 自体が使えない(サーバーがないため)。
  // かわりにFastAPIが同一オリジンで /api/* をそのまま処理する。
  ...(STATIC_EXPORT
    ? {}
    : {
        async rewrites() {
          return [{ source: "/api/:path*", destination: `${API_BASE}/api/:path*` }];
        },
      }),
};

export default nextConfig;

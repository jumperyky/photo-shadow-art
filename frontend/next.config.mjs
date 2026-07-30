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

const nextConfig = {
  reactStrictMode: true,
  ...(allowedDevOrigins.length > 0 ? { allowedDevOrigins } : {}),
  // /api/* をPython APIへプロキシする。フロントからは常に同一オリジンで叩けるので
  // CORSやAPI URLの環境差を気にしなくてよい。
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_BASE}/api/:path*` }];
  },
};

export default nextConfig;

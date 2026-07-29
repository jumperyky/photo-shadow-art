/** @type {import('next').NextConfig} */

// バックエンド(FastAPI)のURL。開発時は localhost:8000。
const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // /api/* をPython APIへプロキシする。フロントからは常に同一オリジンで叩けるので
  // CORSやAPI URLの環境差を気にしなくてよい。
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_BASE}/api/:path*` }];
  },
};

export default nextConfig;

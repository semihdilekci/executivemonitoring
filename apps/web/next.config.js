/** @type {import('next').NextConfig} */

// Tarayıcıdan gelen /api/v1/* istekleri (axios apiClient) Next üzerinden yerel
// FastAPI'ye proxy'lenir. Bu sayede ngrok tek-tünel paylaşımında tarayıcı her
// şeyi aynı origin'den görür → CORS yok, tek link. Normal local dev'de
// NEXT_PUBLIC_API_BASE_URL absolute (localhost:8000) olduğunda bu rewrite
// kullanılmaz; eklenmesi mevcut akışı bozmaz.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_PROXY_TARGET}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

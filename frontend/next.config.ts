import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    // Local dev only: proxy /api/* to the FastAPI backend. In Vercel
    // production we'll either move the backend into frontend/api/ or set
    // BACKEND_URL to the deployed function URL.
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
    ];
  },
};

export default nextConfig;

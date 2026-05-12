import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // In production (Vercel), /api/predict is served directly by the Python
    // serverless function at frontend/api/predict.py -- no rewrite needed.
    // For local `next dev`, set BACKEND_URL=http://127.0.0.1:8000 in
    // .env.local to proxy /api/* to a locally-running uvicorn.
    const backend = process.env.BACKEND_URL;
    if (!backend) return [];
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
    ];
  },
};

export default nextConfig;

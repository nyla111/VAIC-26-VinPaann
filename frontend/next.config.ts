import type { NextConfig } from "next";

const backendUrl = process.env.NEXT_PUBLIC_VAIC_API_BASE_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/vaic/:path*",
        destination: `${backendUrl}/dashboard/api/:path*`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: "/api/hub/:path*",
        destination: `${backendUrl}/api/hub/:path*`,
      },

    ];

  },
};

export default nextConfig;

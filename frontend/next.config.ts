import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Long-running API calls (section planning, batch generation) can take
  // minutes. Node's default HTTP agent drops idle sockets well before that,
  // which surfaces as "socket hang up / ECONNRESET" in the dev proxy.
  // 10 minutes is generous enough for any LLM batch workload.
  experimental: {
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const api = process.env.API_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
  agentRules: false,
  // the rewrite proxy times out at 30 s by default, same as the Claude call; leave headroom
  experimental: { proxyTimeout: 60_000 },
};

export default nextConfig;

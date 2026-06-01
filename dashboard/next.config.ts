import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Allow mapbox-gl to be bundled
  transpilePackages: ["@tremor/react"],
};

export default nextConfig;

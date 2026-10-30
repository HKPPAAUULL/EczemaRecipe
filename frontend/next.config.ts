import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  // classic request-time rendering (no Cache Components/PPR): data pages are
  // API-backed and always fetched per request, and notFound() must yield a
  // real 404 status rather than a streamed 200 shell
  cacheComponents: false,
  partialPrefetching: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

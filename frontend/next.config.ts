import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A separate build folder (e.g. NEXT_DIST_DIR=.next-prod) lets a production build run
  // next to `npm run dev` without the two overwriting each other.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  cacheComponents: true,
  partialPrefetching: true,
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

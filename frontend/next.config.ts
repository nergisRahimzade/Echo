import type { NextConfig } from "next";

// On a host (Render, Vercel, CI) the API address must be given at build time: without it the
// site would quietly call http://localhost:8000 and every request would fail on phones.
const hosted = Boolean(process.env.RENDER || process.env.VERCEL || process.env.CI);
if (hosted && process.env.NODE_ENV !== "development" && !process.env.NEXT_PUBLIC_API_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set. Set it to the API's address (e.g. https://echo-api.onrender.com) and build again.",
  );
}

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

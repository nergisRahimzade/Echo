import type { MetadataRoute } from "next";

/** Web app manifest: lets users "Add to Home Screen" so Echo opens like a native app. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Echo",
    short_name: "Echo",
    description: "Your personal speech interpreter.",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#fbf8f3",
    theme_color: "#1f5eff",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
  };
}

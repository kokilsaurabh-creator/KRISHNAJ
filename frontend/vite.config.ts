import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Krishna Jewellers",
        short_name: "KJ ERP",
        description: "Ledger, sales, purchases and payments for Krishna Jewellers",
        theme_color: "#7a1f3d",
        background_color: "#faf7f2",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.method === "GET",
            handler: "StaleWhileRevalidate",
            options: { cacheName: "api-get-cache" },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
  },
});

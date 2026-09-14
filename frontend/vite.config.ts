import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // PNG icons in every required size are generated from the teal icon
      // SVG. The minimal-2023 preset pads the maskable variant so Android's
      // circular crop can't clip the feather.
      pwaAssets: { config: true },
      manifest: {
        name: "Krishna Jewellers",
        short_name: "KJ ERP",
        description: "Ledger, sales, purchases and payments for Krishna Jewellers",
        theme_color: "#0F6E56",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: "/",
      },
      workbox: {
        // pdfmake and its fonts are ~2 MB — most of the app's weight, for a
        // feature many sessions never touch. Keeping them out of the
        // precache keeps the install small; they're cached on first export
        // instead. A ledger can't be read offline anyway, so there's nothing
        // to export offline either.
        globIgnores: ["**/pdfmake-*.js", "**/vfs_fonts-*.js"],
        runtimeCaching: [
          {
            urlPattern: /\/assets\/(pdfmake|vfs_fonts)-[\w-]+\.js$/,
            handler: "CacheFirst",
            options: {
              cacheName: "pdf-export-lib",
              expiration: { maxEntries: 4 },
            },
          },
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

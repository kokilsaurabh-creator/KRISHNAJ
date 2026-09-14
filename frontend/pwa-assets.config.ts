import { defineConfig, minimal2023Preset } from "@vite-pwa/assets-generator/config";

/**
 * Icon generation from the teal app icon.
 *
 * The preset pads the artwork so the feather stays inside the maskable
 * safe zone (Android crops maskable icons to a circle). Its default pads
 * with white, which would leave a white ring around the teal tile once
 * cropped — so the padding is filled with the brand teal instead, letting
 * the background bleed to the edge on every device shape.
 */
export default defineConfig({
  headLinkOptions: { preset: "2023" },
  preset: {
    ...minimal2023Preset,
    maskable: {
      ...minimal2023Preset.maskable,
      resizeOptions: { ...minimal2023Preset.maskable.resizeOptions, background: "#0F6E56" },
    },
    apple: {
      ...minimal2023Preset.apple,
      resizeOptions: { ...minimal2023Preset.apple.resizeOptions, background: "#0F6E56" },
    },
  },
  images: ["public/krishna-jewellers-icon-teal.svg"],
});

import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { FontaineTransform } from "fontaine";
import path from "node:path";

// Preloads exactly two fonts (DESIGN_SYSTEM 2.3): Public Sans latin variable and Plex Mono latin 500.
const PRELOAD_PREFIXES = ["public-sans-latin-wght-normal", "ibm-plex-mono-latin-500-normal"];

function preloadFonts(): Plugin {
  return {
    name: "preload-fonts",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        const bundle = ctx.bundle ?? {};
        return Object.keys(bundle)
          .filter((file) => file.endsWith(".woff2"))
          .filter((file) =>
            PRELOAD_PREFIXES.some((prefix) => path.basename(file).startsWith(prefix)),
          )
          .map((file) => ({
            tag: "link",
            attrs: {
              rel: "preload",
              as: "font",
              type: "font/woff2",
              crossorigin: "",
              href: `/${file}`,
            },
            injectTo: "head" as const,
          }));
      },
    },
  };
}

export default defineConfig({
  build: { manifest: true },
  plugins: [
    react(),
    tailwindcss(),
    FontaineTransform.vite({
      fallbacks: {
        "Public Sans Variable": ["Arial"],
        "IBM Plex Mono": ["Courier New"],
      },
      fallbackName: (name) => `${name.replace(/ Variable$/, "")} Fallback`,
    }),
    preloadFonts(),
  ],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    env: { VITE_API_BASE_URL: "http://api.test" },
  },
});

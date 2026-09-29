import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:4173",
    headless: false,
    launchOptions: { slowMo: 350 },
  },
});

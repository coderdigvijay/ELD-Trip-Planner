import { defineConfig } from "@playwright/test";

const PORT = 5199;

// Headed on purpose (CLAUDE.md): tests run in their own window; CI wraps the run in xvfb-run.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 2,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${String(PORT)}`,
    headless: false,
    launchOptions: { slowMo: 100 },
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `npm run dev -- --port ${String(PORT)} --strictPort`,
    url: `http://localhost:${String(PORT)}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});

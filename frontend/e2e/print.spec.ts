import { chromium, expect, test } from "@playwright/test";

import { attachGuard } from "./helpers/guards";
import { fixtures, mockApi } from "./helpers/mockApi";

// page.pdf() exists only in headless Chromium, so this one test drives its own headless browser.
test("print media renders one PDF page per log sheet", async ({ baseURL }) => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ baseURL: baseURL ?? "" });
    const guard = attachGuard(page);
    guard.allowAbort(/\/api\/v1\/health/); // dev StrictMode aborts the first warm-up ping
    await mockApi(page, { kind: "ok", body: fixtures.multiDayTrip });

    await page.goto("/");
    await page.getByLabel("Current location").fill("Richmond, VA");
    await page.getByLabel("Pickup").fill("Columbus, OH");
    await page.getByLabel("Dropoff").fill("Chicago, IL");
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Plan trip" }).click();
    await expect(page.getByRole("tab", { name: /^Day 1/ })).toBeVisible();

    await page.emulateMedia({ media: "print" });
    // Print logs mounts every sheet on beforeprint; page.pdf() does not fire it, so fire it here.
    await page.evaluate(() => window.dispatchEvent(new Event("beforeprint")));
    await expect(page.getByTestId("print-all-logs")).toBeAttached();
    const pdf = await page.pdf({ preferCSSPageSize: true });

    const pages = pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) ?? [];
    expect(pages).toHaveLength(fixtures.multiDayTrip.summary.sheet_count);
    expect(guard.problems()).toEqual([]);
  } finally {
    await browser.close();
  }
});

import { chromium, expect, test } from "@playwright/test";

import { attachGuard } from "./helpers/guards";
import { fixtures, mockApi } from "./helpers/mockApi";

// Printable width of a letter page with 0.4 in margins: 7.7 in = 739.2 CSS px (logs.css @page).
const PRINTABLE_PX = 7.7 * 96;

// page.pdf() exists only in headless Chromium, so these tests drive their own headless browser.
for (const viewportWidth of [1280, 360]) {
  test(`print media renders one bare PDF page per log sheet (planned at ${String(viewportWidth)} px)`, async ({
    baseURL,
  }) => {
    await printCheck(baseURL ?? "", viewportWidth);
  });
}

async function printCheck(baseURL: string, viewportWidth: number): Promise<void> {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({
      baseURL,
      viewport: { width: viewportWidth, height: 800 },
    });
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
    // No app chrome on paper: the app root is hidden and only the sheets are laid out.
    const printed = await page.evaluate(() => document.body.innerText);
    expect(printed).not.toMatch(/daily logs|plan trip|day 1/i);
    // Lay the page out at the printable width, as the print engine does: each sheet fills it exactly.
    await page.setViewportSize({ width: Math.round(PRINTABLE_PX), height: 1000 });
    const widths = await page.evaluate(() =>
      Array.from(document.querySelectorAll(".log-sheet-page svg")).map(
        (svg) => svg.getBoundingClientRect().width,
      ),
    );
    expect(widths).toHaveLength(fixtures.multiDayTrip.summary.sheet_count);
    for (const width of widths) expect(width).toBeCloseTo(PRINTABLE_PX, 0);

    // page.pdf() ends print emulation with afterprint (the sheets unmount), so it comes last.
    const pdf = await page.pdf({ preferCSSPageSize: true });
    const pages = pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) ?? [];
    expect(pages).toHaveLength(fixtures.multiDayTrip.summary.sheet_count);
    expect(guard.problems()).toEqual([]);
  } finally {
    await browser.close();
  }
}

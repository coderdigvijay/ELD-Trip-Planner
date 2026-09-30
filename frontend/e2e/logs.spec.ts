import type { Page } from "@playwright/test";

import { fixtures } from "./helpers/mockApi";
import { expect, expectResults, fillTrip, planTrip, test } from "./helpers/test";

test.beforeEach(({ api }) => {
  api.setPlanReplies({ kind: "ok", body: fixtures.multiDayTrip });
});

async function openLogs(page: Page, width: number): Promise<void> {
  await page.setViewportSize({ width, height: 900 });
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);
  await expect(page.getByTestId("sheet-frame")).toBeVisible();
}

const scrollRegion = (page: Page) =>
  page.getByRole("region", { name: "Log sheet, scroll horizontally" });

for (const [width, sheet] of [
  [1024, { min: 900, max: 1000 }],
  [1440, { min: 1200, max: 1200 }],
] as const) {
  test(`sheet is fluid at ${String(width)} px (container query, no scroll region)`, async ({
    page,
  }) => {
    await openLogs(page, width);
    await expect(scrollRegion(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Fit width" })).toHaveCount(0);
    const frame = await page.getByTestId("sheet-frame").boundingBox();
    expect(frame?.width ?? 0).toBeGreaterThanOrEqual(sheet.min);
    expect(frame?.width ?? 0).toBeLessThanOrEqual(sheet.max);
    // The svg fills the frame; the page never scrolls sideways.
    const svg = await page.getByRole("img", { name: /^Driver's daily log/ }).boundingBox();
    expect(svg?.width).toBeCloseTo(frame?.width ?? 0, 0);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test("at 360 px the sheet is a fixed 960 px scroll region; scrollLeft survives day tabs; Fit width toggles", async ({
  page,
}) => {
  await openLogs(page, 360);
  const region = scrollRegion(page);
  await expect(region).toHaveAttribute("tabindex", "0");
  expect((await page.getByTestId("sheet-frame").boundingBox())?.width).toBeCloseTo(960, 0);

  await region.evaluate((el) => {
    el.scrollLeft = 300;
  });
  await page.getByRole("tab", { name: /^Day 2/ }).click();
  await expect(page.getByRole("tab", { name: /^Day 2/ })).toHaveAttribute("aria-selected", "true");
  expect(await region.evaluate((el) => el.scrollLeft)).toBe(300);
  await page.getByRole("tab", { name: /^Day 3/ }).click();
  expect(await region.evaluate((el) => el.scrollLeft)).toBe(300);

  await page.getByRole("button", { name: "Fit width" }).click();
  await expect(scrollRegion(page)).toHaveCount(0);
  const frame = await page.getByTestId("sheet-frame").boundingBox();
  expect(frame?.width ?? 0).toBeLessThan(360);
  await page.getByRole("button", { name: "Actual size" }).click();
  await expect(scrollRegion(page)).toBeVisible();
});

test("the tab panel is not a tab stop and every stop shows a focus ring", async ({ page }) => {
  await openLogs(page, 1280);
  await page.getByRole("tab", { name: /^Day 1/ }).focus();
  const stops: string[] = [];
  for (let i = 0; i < 8; i += 1) {
    await page.keyboard.press("Tab");
    const stop = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return "body";
      const style = getComputedStyle(el);
      const ring = style.outlineStyle !== "none" || style.boxShadow !== "none";
      const name = el.getAttribute("role") ?? el.tagName.toLowerCase();
      return `${name}|${el.textContent.trim().slice(0, 24)}|ring:${String(ring)}`;
    });
    stops.push(stop);
    if (stop.startsWith("summary")) break;
  }
  expect(stops.some((s) => s.startsWith("tabpanel"))).toBe(false);
  expect(stops.at(-1)).toMatch(/^summary\|Show table\|ring:true$/);
  expect(stops.every((s) => s.endsWith("ring:true"))).toBe(true);
});

test("Download PDF embeds IBM Plex Mono for every run and warns about nothing", async ({
  page,
}) => {
  await openLogs(page, 1280);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF" }).click();
  const download = await downloadPromise;
  const path = await download.path();
  const { readFileSync } = await import("node:fs");
  const pdf = readFileSync(path).toString("latin1");
  // jsPDF lists its 14 standard fonts as F1 to F14 in every file; ours are registered after them.
  const baseFonts = [...pdf.matchAll(/\/BaseFont\s*\/(\S+)/g)].map((m) => String(m[1]));
  expect(baseFonts.filter((f) => /Public#20Sans/.test(f))).toHaveLength(4);
  expect(baseFonts.filter((f) => /IBM#20Plex#20Mono/.test(f))).toHaveLength(4);
  // Text set in a font resource: only our four embedded fonts (sans regular and bold, mono regular and bold).
  const used = new Set([...pdf.matchAll(/\/F(\d+) [\d.]+ Tf/g)].map((m) => Number(m[1])));
  expect(used.size).toBe(4);
  expect(Math.min(...used)).toBeGreaterThan(14);
  expect((pdf.match(/\/Type\s*\/Page[^s]/g) ?? []).length).toBe(3);
  // The guard fixture fails the test on any jsPDF "Unable to look up font" console warning.
});

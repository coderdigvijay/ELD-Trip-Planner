import type { Page } from "@playwright/test";

import { fixtures } from "./helpers/mockApi";
import { expect, expectResults, fillTrip, planTrip, test } from "./helpers/test";

const CLS_BUDGET = 0.1;
const PLAN_LATENCY_MS = 1200;

/** Sums layout shifts that were not caused by input, from the moment `reset()` is called. */
async function trackLayoutShift(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const w = window as unknown as { __cls: number; __clsReset: () => void };
    w.__cls = 0;
    w.__clsReset = () => {
      w.__cls = 0;
    };
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (!shift.hadRecentInput) w.__cls += shift.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
}

const readShift = (page: Page) =>
  page.evaluate(() => (window as unknown as { __cls: number }).__cls);

/** The multi-day fixture with `count` stops, so the Stops panel has far more rows than fit. */
function withManyStops(count: number): unknown {
  const base = structuredClone(fixtures.multiDayTrip);
  const template = base.stops[3];
  if (!template) throw new Error("fixture has no stop to copy");
  base.stops = Array.from({ length: count }, (_, i) => ({ ...template, id: `m${String(i)}` }));
  return base;
}

async function planWithLatency(page: Page) {
  await page.route("**/api/v1/trips/plan", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, PLAN_LATENCY_MS));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(fixtures.multiDayTrip),
    });
  });
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "360", width: 360, height: 800 },
  // Tall windows put the whole page in view, so shifts below the fold count too (worst case).
  { name: "desktop, whole page in view", width: 1440, height: 2600 },
  { name: "360, whole page in view", width: 360, height: 4200 },
  { name: "768, whole page in view", width: 768, height: 3400 },
  { name: "1024, whole page in view", width: 1024, height: 3000 },
]) {
  test(`landing a plan shifts the layout by at most ${String(CLS_BUDGET)} at ${viewport.name}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await trackLayoutShift(page);
    await planWithLatency(page);
    await page.goto("/");
    await fillTrip(page);
    await page.evaluate(() => {
      (window as unknown as { __clsReset: () => void }).__clsReset();
    });
    await planTrip(page);
    await expectResults(page);
    await expect(page.locator(".leaflet-marker-icon").first()).toBeVisible();
    await expect(page.locator('.log-sheet-page svg, svg[role="img"]').first()).toBeVisible();
    // Let the 160 ms reveal and any late tile or font work finish.
    await page.waitForTimeout(1000);
    const shift = await readShift(page);
    console.log(`CLS ${viewport.name}: ${shift.toFixed(4)}`);
    expect(shift).toBeLessThanOrEqual(CLS_BUDGET);
  });
}

test("the route is drawn as a 4 px pen line over a 7 px surface casing, first leg dashed", async ({
  page,
  api,
}) => {
  api.setPlanReplies({ kind: "ok", body: fixtures.multiDayTrip });
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);
  await expect(page.locator("path.route-line")).toHaveCount(2);

  const strokes = await page.evaluate(() => {
    const read = (selector: string) =>
      [...document.querySelectorAll<SVGPathElement>(selector)].map((path) => {
        const style = getComputedStyle(path);
        return { stroke: style.stroke, width: style.strokeWidth, dash: style.strokeDasharray };
      });
    const probe = document.createElement("span");
    document.body.append(probe);
    const color = (token: string) => {
      probe.style.color = `var(${token})`;
      return getComputedStyle(probe).color;
    };
    const tokens = { pen: color("--color-pen"), surface: color("--color-surface") };
    probe.remove();
    return { line: read("path.route-line"), casing: read("path.route-casing"), tokens };
  });

  expect(strokes.tokens.pen).not.toBe(strokes.tokens.surface);
  for (const line of strokes.line) {
    expect(line.stroke).toBe(strokes.tokens.pen);
    expect(line.width).toBe("4px");
  }
  for (const casing of strokes.casing) {
    expect(casing.stroke).toBe(strokes.tokens.surface);
    expect(casing.width).toBe("7px");
  }
  expect(strokes.line[0]?.dash).toMatch(/^8(px)?,? 6(px)?$/);
  expect(strokes.line[1]?.dash).toBe("none");
});

test("at 1440 the Stops card is 400 px with its list scrolling inside, and the Route card does not stretch", async ({
  page,
  api,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  api.setPlanReplies({ kind: "ok", body: withManyStops(56) });
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);

  const stops = page.getByRole("region", { name: "Stops", exact: true });
  const route = page.getByRole("region", { name: "Route", exact: true });
  await expect(stops).toBeVisible();
  const stopsBox = await stops.boundingBox();
  const routeBox = await route.boundingBox();
  expect(stopsBox?.height).toBe(400);
  expect(routeBox?.height).toBeLessThan(600);

  const timeline = page.getByRole("region", { name: "Trip timeline" });
  await expect(timeline).toHaveAttribute("tabindex", "0");
  const scroll = await timeline.evaluate((el) => ({
    scrollable: el.scrollHeight > el.clientHeight,
    overflowY: getComputedStyle(el).overflowY,
  }));
  expect(scroll).toEqual({ scrollable: true, overflowY: "auto" });

  // Keyboard reachable: focus the region and scroll it with the arrow keys.
  await timeline.focus();
  await expect(timeline).toBeFocused();
  await page.keyboard.press("PageDown");
  await expect.poll(() => timeline.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
});

test("at 1024 the Stops card is 480 px tall", async ({ page, api }) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  api.setPlanReplies({ kind: "ok", body: withManyStops(56) });
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);
  const box = await page.getByRole("region", { name: "Stops", exact: true }).boundingBox();
  expect(box?.height).toBe(480);
});

test("Print logs sits in the header on phones once results exist, and not on desktop", async ({
  page,
  api,
}) => {
  api.setPlanReplies({ kind: "ok", body: fixtures.multiDayTrip });
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  const header = page.getByRole("banner");
  await expect(header.getByRole("button", { name: "Print logs" })).toHaveCount(0);
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);
  await expect(header.getByRole("button", { name: "Print logs" })).toBeVisible();

  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(header.getByRole("button", { name: "Print logs" })).toBeHidden();
});

test("the document preconnects to the API origin", async ({ page }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="preconnect"]').getAttribute("href");
  expect(href).toMatch(/^https?:\/\/[^/]+$/);
  await expect(page.locator('link[rel="preconnect"]')).toHaveAttribute("crossorigin", "");
});

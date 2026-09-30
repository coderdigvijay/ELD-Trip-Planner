import type { Page } from "@playwright/test";

import { fixtures } from "./helpers/mockApi";
import { expect, expectResults, fillTrip, planTrip, test } from "./helpers/test";

const MAX_TABS = 150;

/** Presses Tab until `target` has focus; fails if it is not reachable within MAX_TABS presses. */
async function tabTo(page: Page, target: ReturnType<Page["locator"]>): Promise<void> {
  for (let press = 0; press < MAX_TABS; press += 1) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((el) => el === document.activeElement)) return;
  }
  throw new Error("target was not reached by Tab");
}

test("keyboard only: first field to Print logs", async ({ page, api }) => {
  api.setPlanReplies({ kind: "ok", body: fixtures.multiDayTrip });
  await page.goto("/");
  await page.getByLabel("Current location").focus();

  const pageFields = [
    ["Current location", "Richmond, VA"],
    ["Pickup", "Baltimore, MD"],
    ["Dropoff", "Newark, NJ"],
  ] as const;
  for (const [index, [label, value]] of pageFields.entries()) {
    const field = page.getByLabel(label);
    await expect(field).toBeFocused();
    await page.keyboard.type(value);
    await page.keyboard.press("Escape");
    if (index < pageFields.length - 1) await page.keyboard.press("Tab");
  }
  await tabTo(page, page.getByRole("button", { name: "Plan trip" }));
  await page.keyboard.press("Enter");
  await expectResults(page);

  const firstTab = page.getByRole("tab", { name: /^Day 1/ });
  await tabTo(page, firstTab);
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /^Day 2/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tab", { name: /^Day 2/ })).toBeFocused();

  await tabTo(page, page.getByRole("button", { name: "Print logs" }));
  await expect(page.getByRole("button", { name: "Print logs" })).toBeFocused();
  const outline = await page
    .getByRole("button", { name: "Print logs" })
    .evaluate((el) => getComputedStyle(el).outlineStyle + getComputedStyle(el).boxShadow);
  expect(outline).not.toMatch(/^none(none)?$/);
});

test("360 px viewport has no horizontal page scroll, before and after planning", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 740 });
  const overflow = () =>
    page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );

  await page.goto("/");
  await expect(page.getByLabel("Current location")).toBeVisible();
  expect(await overflow()).toBeLessThanOrEqual(0);

  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);
  expect(await overflow()).toBeLessThanOrEqual(0);
});

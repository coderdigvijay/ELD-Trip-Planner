import { expect, test as base, type Page } from "@playwright/test";

import { attachGuard, type Guard } from "./guards";
import { fixtures, mockApi, type MockApi } from "./mockApi";

interface Fixtures {
  guard: Guard;
  api: MockApi;
}

/** Every test gets the API mocked (short trip by default) and a guard that must end empty. */
export const test = base.extend<Fixtures>({
  guard: [
    async ({ page }, provide) => {
      const guard = attachGuard(page);
      // Dev-only: React StrictMode remounts the warm-up query, which aborts its first ping.
      guard.allowAbort(/\/api\/v1\/health$/);
      await provide(guard);
      expect(guard.problems(), "console, page, request or HTTP problems").toEqual([]);
    },
    { auto: true },
  ],
  api: [
    async ({ page }, provide) => {
      await provide(await mockApi(page, { kind: "ok", body: fixtures.shortTrip }));
    },
    { auto: true },
  ],
});

export { expect };

const TRIP = {
  current: "Richmond, VA",
  pickup: "Baltimore, MD",
  dropoff: "Newark, NJ",
} as const;

/** Types the three places as free text (no suggestion picked) and leaves the cycle at its default. */
export async function fillTrip(page: Page): Promise<void> {
  await page.getByLabel("Current location").fill(TRIP.current);
  await page.getByLabel("Pickup").fill(TRIP.pickup);
  await page.getByLabel("Dropoff").fill(TRIP.dropoff);
  // The suggestion popup of the last field would cover the submit button.
  await page.keyboard.press("Escape");
}

export async function planTrip(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Plan trip" }).click();
}

/** The results region, once the summary heading is on screen. */
export async function expectResults(page: Page): Promise<void> {
  await expect(page.getByRole("region", { name: "Summary" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Day 1/ })).toBeVisible();
}

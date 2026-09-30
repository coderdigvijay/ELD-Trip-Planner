import { expect, expectResults, fillTrip, planTrip, test } from "./helpers/test";
import { fixtures } from "./helpers/mockApi";

test.beforeEach(({ api }) => {
  api.setPlanReplies({ kind: "ok", body: fixtures.multiDayTrip });
});

test("multi-day trip: several day tabs, each sheet totals 24", async ({ page }) => {
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);

  const tabs = page.getByRole("tab", { name: /^Day \d/ });
  await expect(tabs).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    await tabs.nth(index).click();
    await expect(tabs.nth(index)).toHaveAttribute("aria-selected", "true");
    // The totals table sits in a closed disclosure; its text is in the DOM either way.
    await expect(
      page.locator('table:has(caption:text("Total hours")) tbody tr:last-child td'),
    ).toHaveText(/^24(\.00)?$/);
  }
});

test("clicking a stop selects its marker and switches the log to that day", async ({ page }) => {
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);
  await expect(page.getByRole("tab", { name: /^Day 1/ })).toHaveAttribute("aria-selected", "true");

  const row = page.locator('[data-stop-id="s5"] button');
  await row.click();

  await expect(row).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("tab", { name: /^Day 2/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('.leaflet-marker-icon[aria-pressed="true"]')).toHaveCount(1);
});

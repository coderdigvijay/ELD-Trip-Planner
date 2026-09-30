import { expect, expectResults, fillTrip, planTrip, test } from "./helpers/test";

test("first visit shows guidance and the example button only fills the form", async ({
  page,
  api,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Plan a trip to get its route, stops and daily logs." }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Fill an example trip" }).click();

  await expect(page.getByLabel("Current location")).toHaveValue("Richmond, VA");
  await expect(page.getByLabel("Pickup")).toHaveValue("Chicago, IL");
  await expect(page.getByLabel("Dropoff")).toHaveValue("Denver, CO");
  await expect(page.getByRole("button", { name: "Plan trip" })).toBeFocused();
  expect(api.planRequests).toHaveLength(0);
});

test("type, pick a suggestion, submit and see summary, stops, map and logs", async ({
  page,
  api,
}) => {
  await page.goto("/");
  const current = page.getByLabel("Current location");
  await current.fill("Rich");
  await page.getByRole("option", { name: /Richmond, VA, USA/ }).click();
  await expect(current).toHaveValue("Richmond, VA, USA");
  await page.getByLabel("Pickup").fill("Baltimore, MD");
  await page.getByLabel("Dropoff").fill("Newark, NJ");
  await page.keyboard.press("Escape");
  await planTrip(page);

  await expectResults(page);
  const summary = page.getByRole("region", { name: "Summary" });
  await expect(summary.getByText("Daily logs")).toBeVisible();
  await expect(summary.getByText("338 mi")).toBeVisible();

  const stops = page.getByRole("region", { name: "Stops" });
  await expect(stops.locator('[data-stop-id="s2"] button')).toBeVisible();
  await expect(page.getByRole("region", { name: /^Route map/ })).toBeVisible();
  await expect(page.locator(".leaflet-marker-icon").first()).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Day 1/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "Print logs" })).toBeVisible();

  expect(api.planRequests).toHaveLength(1);
  expect(api.planRequests[0]).toMatchObject({
    current_location: { lat: 37.54072, lng: -77.43605 },
    pickup_location: "Baltimore, MD",
    dropoff_location: "Newark, NJ",
  });
});

test("a cold server shows the waking state, then the results once health answers", async ({
  page,
  api,
}) => {
  const health = api.holdHealth();
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);

  const waking = page.getByRole("group", { name: "Starting the server" });
  await expect(waking).toBeVisible();
  await expect(waking.getByText(/^Waiting [1-9]\d* s$/)).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Day 1/ })).toHaveCount(0);

  health.release();
  await expectResults(page);
  await expect(waking).toHaveCount(0);
});

test("Cancel while the server wakes restores the form", async ({ page, api }) => {
  const health = api.holdHealth();
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);

  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("button", { name: "Plan trip" })).toBeEnabled();
  await expect(page.getByLabel("Pickup")).toHaveValue("Baltimore, MD");
  health.release();
});

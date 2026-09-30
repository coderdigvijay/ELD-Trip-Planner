import { expect, expectResults, fillTrip, planTrip, test } from "./helpers/test";
import { fixtures } from "./helpers/mockApi";

const PLAN_URL = /\/api\/v1\/trips\/plan$/;

test("LOCATION_NOT_FOUND names the field, focuses it and keeps the values", async ({
  page,
  api,
  guard,
}) => {
  guard.allowHttpError({ url: PLAN_URL, status: 422 });
  const message =
    'We couldn\'t find "Nowhereville, ZZ". Check the spelling or pick a suggestion from the list.';
  api.setPlanReplies({
    kind: "error",
    status: 422,
    error: {
      code: "LOCATION_NOT_FOUND",
      message,
      field: "pickup_location",
      request_id: "7f3c2a9e1b4d4c0e",
    },
  });
  await page.goto("/");
  await fillTrip(page);
  await page.getByLabel("Pickup").fill("Nowhereville, ZZ");
  await page.keyboard.press("Escape");
  await planTrip(page);

  await expect(page.getByText(message)).toBeVisible();
  await expect(page.getByLabel("Pickup")).toBeFocused();
  await expect(page.getByLabel("Pickup")).toHaveValue("Nowhereville, ZZ");
  await expect(page.getByLabel("Current location")).toHaveValue("Richmond, VA");
});

test("RATE_LIMITED shows a countdown, then Try again is enabled", async ({ page, api, guard }) => {
  guard.allowHttpError({ url: PLAN_URL, status: 429 });
  api.setPlanReplies(
    {
      kind: "error",
      status: 429,
      headers: { "retry-after": "3" },
      error: {
        code: "RATE_LIMITED",
        message: "Too many trip plans from your network. Wait 3 seconds, then try again.",
        retry_after_s: 3,
        request_id: "0b9d1c7e5a3f4e21",
      },
    },
    { kind: "ok", body: fixtures.shortTrip },
  );
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);

  const retry = page.getByRole("button", { name: "Try again" });
  await expect(page.getByText(/You can plan again in [1-3] s\./)).toBeVisible();
  await expect(retry).toBeDisabled();
  await expect(retry).toBeEnabled();
});

test("UPSTREAM_UNAVAILABLE offers Try again and the second call succeeds", async ({
  page,
  api,
  guard,
}) => {
  guard.allowHttpError({ url: PLAN_URL, status: 503 });
  api.setPlanReplies(
    {
      kind: "error",
      status: 503,
      error: {
        code: "UPSTREAM_UNAVAILABLE",
        message: "The routing service is not responding. Try again in a minute.",
        request_id: "1a2b3c4d5e6f7a8b",
      },
    },
    { kind: "ok", body: fixtures.shortTrip },
  );
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);

  await expect(page.getByText("The routing service is not responding")).toBeVisible();
  await page.getByRole("button", { name: "Try again" }).click();

  await expectResults(page);
  await expect(page.getByText("The routing service is not responding")).toHaveCount(0);
  expect(api.planRequests).toHaveLength(2);
});

import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, expectResults, fillTrip, planTrip, test } from "./helpers/test";

const SECRET_PATTERN = /api_key/i;

test("no request carries an API key", async ({ page }) => {
  const seen: string[] = [];
  page.on("request", (request) => {
    seen.push(
      `${request.url()}\n${JSON.stringify(request.headers())}\n${request.postData() ?? ""}`,
    );
  });
  await page.goto("/");
  await fillTrip(page);
  await planTrip(page);
  await expectResults(page);

  expect(seen.length).toBeGreaterThan(0);
  expect(seen.filter((entry) => SECRET_PATTERN.test(entry))).toEqual([]);
});

test("the built bundle does not contain an api_key string", () => {
  const assets = path.join(import.meta.dirname, "..", "dist", "assets");
  test.skip(!existsSync(assets), "run `npm run build` first");
  const offenders = readdirSync(assets)
    .filter((file) => file.endsWith(".js"))
    .filter((file) => SECRET_PATTERN.test(readFileSync(path.join(assets, file), "utf8")));
  expect(offenders).toEqual([]);
});

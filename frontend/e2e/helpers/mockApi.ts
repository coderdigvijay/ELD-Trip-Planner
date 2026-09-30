import type { Page, Route } from "@playwright/test";

import autocomplete from "../fixtures/autocomplete.json" with { type: "json" };
import multiDayTrip from "../fixtures/multiDayTrip.json" with { type: "json" };
import shortTrip from "../fixtures/shortTrip.json" with { type: "json" };

export const fixtures = { shortTrip, multiDayTrip, autocomplete } as const;

export interface ApiErrorBody {
  code: string;
  message: string;
  field?: string;
  retry_after_s?: number;
  request_id?: string;
}

/** One scripted reply to POST /trips/plan. */
export type PlanReply =
  | { kind: "ok"; body: unknown }
  | { kind: "error"; status: number; error: ApiErrorBody; headers?: Record<string, string> };

export interface MockApi {
  /** Bodies of every POST /trips/plan seen, in order. */
  planRequests: unknown[];
  /** Hold GET /health until `release()` (cold Render instance). */
  holdHealth: () => { release: () => void };
  /** Replies for successive plan calls; the last one repeats. */
  setPlanReplies: (...replies: PlanReply[]) => void;
}

// 1x1 transparent PNG so map tiles never hit the network.
const TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

const json = (route: Route, status: number, body: unknown, headers: Record<string, string> = {}) =>
  route.fulfill({
    status,
    contentType: "application/json",
    headers: { "cache-control": "no-store", ...headers },
    body: JSON.stringify(body),
  });

export async function mockApi(page: Page, initial: PlanReply): Promise<MockApi> {
  const planRequests: unknown[] = [];
  let replies: PlanReply[] = [initial];
  let healthGate: Promise<void> | null = null;

  await page.route(
    /\/\/(?:[a-z]\.)?(?:tile\.openstreetmap\.org|basemaps\.cartocdn\.com)\//,
    (route) => route.fulfill({ status: 200, contentType: "image/png", body: TILE }),
  );
  await page.route("**/api/v1/health", async (route) => {
    if (healthGate) await healthGate;
    await json(route, 200, { status: "ok", api_version: "1" });
  });
  await page.route("**/api/v1/places/autocomplete*", (route) =>
    json(route, 200, fixtures.autocomplete),
  );
  await page.route("**/api/v1/trips/plan", async (route) => {
    planRequests.push(route.request().postDataJSON());
    const reply = replies.length > 1 ? replies.shift() : replies[0];
    if (!reply) throw new Error("no plan reply scripted");
    if (reply.kind === "ok") await json(route, 200, reply.body);
    else await json(route, reply.status, { error: reply.error }, reply.headers);
  });

  return {
    planRequests,
    holdHealth: () => {
      let release: () => void = () => undefined;
      healthGate = new Promise<void>((resolve) => {
        release = resolve;
      });
      return { release };
    },
    setPlanReplies: (...next) => {
      replies = next;
    },
  };
}

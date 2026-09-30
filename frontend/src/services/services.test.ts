import { http, HttpResponse } from "msw";

import { server, errorBody } from "@/test/server";

import { ApiError, NetworkError } from "./errors";
import { ping } from "./health";
import { autocomplete } from "./places";
import { planTrip } from "./trips";

beforeAll(() => {
  server.listen();
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

const request = {
  current_location: "Richmond, VA",
  pickup_location: "Baltimore, MD",
  dropoff_location: { label: "Newark, NJ", lat: 40.73566, lng: -74.17237 },
  current_cycle_used_hours: 10,
};

describe("planTrip", () => {
  it("posts the body as JSON and returns the parsed plan", async () => {
    let received: unknown;
    server.use(
      http.post("*/api/v1/trips/plan", async ({ request: req }) => {
        received = await req.json();
        return HttpResponse.json({ summary: { sheet_count: 1 } });
      }),
    );
    const plan = await planTrip(request);
    expect(received).toEqual(request);
    expect(plan.summary.sheet_count).toBe(1);
  });

  it("maps an error envelope to ApiError with code, field, retry and request id", async () => {
    server.use(
      http.post("*/api/v1/trips/plan", () =>
        HttpResponse.json(
          errorBody("RATE_LIMITED", "Wait 42 seconds", {
            retry_after_s: 42,
            field: "pickup_location",
          }),
          { status: 429 },
        ),
      ),
    );
    const error = await planTrip(request).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      code: "RATE_LIMITED",
      status: 429,
      retryAfterS: 42,
      field: "pickup_location",
      requestId: "7f3c2a9e1b4d4c0e",
    });
  });

  it("keeps every validation detail", async () => {
    server.use(
      http.post("*/api/v1/trips/plan", () =>
        HttpResponse.json(
          errorBody("VALIDATION_ERROR", "bad", {
            details: [
              { field: "current_cycle_used_hours", message: "a" },
              { field: "start_time", message: "b" },
            ],
          }),
          { status: 400 },
        ),
      ),
    );
    const error = (await planTrip(request).catch((e: unknown) => e)) as ApiError;
    expect(error.details).toHaveLength(2);
  });

  it("treats a non-JSON 502 page as a bad-response NetworkError", async () => {
    server.use(
      http.post(
        "*/api/v1/trips/plan",
        () => new HttpResponse("<html>Bad gateway</html>", { status: 502 }),
      ),
    );
    const error = await planTrip(request).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NetworkError);
    expect(error).toMatchObject({ reason: "bad-response" });
  });

  it("treats a dropped connection as a NetworkError", async () => {
    server.use(http.post("*/api/v1/trips/plan", () => HttpResponse.error()));
    const error = await planTrip(request).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NetworkError);
  });

  it("rethrows a caller abort untouched", async () => {
    server.use(
      http.post("*/api/v1/trips/plan", async () => {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return HttpResponse.json({});
      }),
    );
    const controller = new AbortController();
    const pending = planTrip(request, controller.signal).catch((e: unknown) => e);
    controller.abort();
    const error = await pending;
    expect(error).not.toBeInstanceOf(NetworkError);
    expect(error).toMatchObject({ name: "AbortError" });
  });
});

describe("autocomplete", () => {
  it("sends q and returns the items", async () => {
    let q: string | null = null;
    server.use(
      http.get("*/api/v1/places/autocomplete", ({ request: req }) => {
        q = new URL(req.url).searchParams.get("q");
        return HttpResponse.json({ items: [{ label: "Richmond, VA", lat: 37.5, lng: -77.4 }] });
      }),
    );
    const items = await autocomplete("Rich");
    expect(q).toBe("Rich");
    expect(items).toEqual([{ label: "Richmond, VA", lat: 37.5, lng: -77.4 }]);
  });

  it("surfaces an upstream failure as ApiError", async () => {
    server.use(
      http.get("*/api/v1/places/autocomplete", () =>
        HttpResponse.json(errorBody("UPSTREAM_UNAVAILABLE", "down"), { status: 503 }),
      ),
    );
    await expect(autocomplete("Rich")).rejects.toMatchObject({ code: "UPSTREAM_UNAVAILABLE" });
  });
});

describe("ping", () => {
  it("resolves on 200 with status ok", async () => {
    server.use(
      http.get("*/api/v1/health", () => HttpResponse.json({ status: "ok", api_version: "1" })),
    );
    await expect(ping()).resolves.toMatchObject({ status: "ok" });
  });

  it("fails on a Render 503 page", async () => {
    server.use(
      http.get("*/api/v1/health", () => new HttpResponse("<html>waking</html>", { status: 503 })),
    );
    await expect(ping()).rejects.toBeInstanceOf(NetworkError);
  });

  it("fails on a 200 that is not JSON", async () => {
    server.use(
      http.get("*/api/v1/health", () => new HttpResponse("<html>ok</html>", { status: 200 })),
    );
    await expect(ping()).rejects.toBeInstanceOf(NetworkError);
  });
});

import { afterEach, vi } from "vitest";

import { createApiClient, normalizeBaseUrl } from "./client";

describe("normalizeBaseUrl", () => {
  it("strips trailing slashes and whitespace", () => {
    expect(normalizeBaseUrl(" https://api.example.com// ")).toBe("https://api.example.com");
  });

  it("returns an empty string when unset", () => {
    expect(normalizeBaseUrl(undefined)).toBe("");
  });
});

describe("createApiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends requests to the configured base URL", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ status: "ok", api_version: "1" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const client = createApiClient("https://api.example.com");
    // openapi-fetch accepts a per-call fetch override.
    await client.GET("/api/v1/health", { fetch: fetchMock });

    const request = fetchMock.mock.calls[0] as unknown as [Request];
    expect(request[0].url).toBe("https://api.example.com/api/v1/health");
  });
});

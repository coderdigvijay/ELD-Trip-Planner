import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "./App";

function testClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

describe("App shell", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ status: "ok", api_version: "1" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the heading structure and the trip panel", async () => {
    render(<App queryClient={testClient()} />);

    expect(screen.getByRole("heading", { level: 1, name: "ELD trip planner" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Trip" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plan trip" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("status")).toBeEmptyDOMElement();
    });
  });

  it("shows the waking notice while the health ping is pending", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    render(<App queryClient={testClient()} />);

    expect(screen.getByRole("status")).toHaveTextContent(/waking the server/i);
  });
});

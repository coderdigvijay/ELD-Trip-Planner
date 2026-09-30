import { QueryClient } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "./App";

function testClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

const fetchMock = vi.fn((input: Request | string) =>
  Promise.resolve(
    new Response(JSON.stringify({ status: "ok", api_version: "1", echo: typeof input }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  ),
);

describe("App shell", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockClear();
    vi.unstubAllGlobals();
  });

  it("renders landmarks, one h1 and the first-visit guidance", () => {
    render(<App queryClient={testClient()} />);

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toHaveTextContent(
      "Not a substitute for a certified ELD.",
    );
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("form", { name: "Trip" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Plan a trip to get its route, stops and daily logs.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Daily logs" })).toBeInTheDocument();
  });

  it("Fill an example trip fills the form only and sends no plan request", async () => {
    const user = userEvent.setup();
    render(<App queryClient={testClient()} />);

    await user.click(screen.getByRole("button", { name: "Fill an example trip" }));

    expect(screen.getByLabelText(/Current location/)).toHaveValue("Richmond, VA");
    expect(screen.getByLabelText(/Dropoff/)).toHaveValue("Denver, CO");
    expect(screen.getByLabelText(/Cycle used/)).toHaveValue("23.5");
    expect(screen.getByRole("button", { name: "Plan trip" })).toHaveFocus();
    const posts = fetchMock.mock.calls.filter(
      ([input]) => typeof input !== "string" && input.method === "POST",
    );
    expect(posts).toHaveLength(0);
  });

  it("shows the server-starting hint only after health has been pending for 3 s", () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    render(<App queryClient={testClient()} />);
    expect(screen.queryByText(/Server starting/)).not.toBeInTheDocument();
    vi.advanceTimersByTime(4000);
    return vi
      .waitFor(() => {
        expect(
          screen.getByText(/Server starting\. The first plan may take a minute\./),
        ).toBeInTheDocument();
      })
      .finally(() => {
        vi.useRealTimers();
      });
  });
});

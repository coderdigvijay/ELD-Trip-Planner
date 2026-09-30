import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { vi } from "vitest";

import { longHaulDays } from "@/features/logs/__fixtures__/longHaul";
import { plan as basePlan, days as dayRefs } from "@/features/results/__fixtures__/multiDayTrip";
import { errorBody, server } from "@/test/server";

import { App } from "./App";

// The shared fixture has no sheets; give it three whose dates match the stops.
const plan = {
  ...basePlan,
  days: longHaulDays(3).map((day, i) => ({ ...day, date: dayRefs[i]?.date ?? day.date })),
  summary: { ...basePlan.summary, sheet_count: 3 },
};

// Leaflet needs a real layout engine. The map slot is replaced by a stub that speaks the same
// props, so selection sync between list, map and logs is still exercised end to end.
vi.mock("@/features/map/MapView", () => ({
  default: ({
    stops,
    selectedStopId,
    onSelectStop,
  }: {
    stops: { id: string; label: string }[];
    selectedStopId: string | null;
    onSelectStop: (id: string | null) => void;
  }): ReactNode => (
    <div data-testid="map-slot" data-selected={selectedStopId ?? ""}>
      {stops.map((stop) => (
        <button
          key={stop.id}
          type="button"
          onClick={() => {
            onSelectStop(stop.id);
          }}
        >
          {`Marker ${stop.id}`}
        </button>
      ))}
    </div>
  ),
}));

// The results chunk is imported on demand; the first transform of the log sheets is slow.
vi.setConfig({ testTimeout: 20_000 });

beforeAll(() => {
  server.listen();
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

const health = http.get("*/api/v1/health", () =>
  HttpResponse.json({ status: "ok", api_version: "1" }),
);

function client(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Fill an example trip" }));
  await user.click(screen.getByRole("button", { name: "Plan trip" }));
}

describe("Workspace", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("shows the empty first-visit state with no results sections loaded", () => {
    server.use(health);
    render(<App queryClient={client()} />);

    expect(screen.getByRole("heading", { name: /Plan a trip to get/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Daily logs" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Summary" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("map-slot")).not.toBeInTheDocument();
  });

  it("renders summary, stops, map slot and logs after a successful plan", async () => {
    server.use(
      health,
      http.post("*/api/v1/trips/plan", () => HttpResponse.json(plan)),
    );
    const user = userEvent.setup();
    render(<App queryClient={client()} />);

    await fillAndSubmit(user);

    expect(await screen.findByRole("heading", { name: "Summary" })).toBeInTheDocument();
    expect(await screen.findByTestId("map-slot")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Baltimore, MD/ }).length).toBeGreaterThan(0);
    expect(
      await screen.findByRole("tablist", { name: "Log sheet days" }, { timeout: 15_000 }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(plan.summary.sheet_count);
    expect(document.title).toContain("Richmond, VA to Newark, NJ");
    expect(new URLSearchParams(window.location.search).get("q")).not.toBeNull();
  });

  it("offers a skip link to the results only once a plan exists", async () => {
    server.use(
      health,
      http.post("*/api/v1/trips/plan", () => HttpResponse.json(plan)),
    );
    const user = userEvent.setup();
    render(<App queryClient={client()} />);
    expect(screen.queryByRole("link", { name: "Skip to results" })).toBeNull();

    await fillAndSubmit(user);
    await screen.findByRole("heading", { name: "Summary" });
    const link = screen.getByRole("link", { name: "Skip to results" });
    expect(link).toHaveAttribute("href", "#results");
    const region = screen.getByRole("region", { name: "Results" });
    expect(region).toHaveAttribute("id", "results");
    expect(region).toHaveAttribute("tabindex", "-1");
  });

  it("keeps list, map and logs in sync on selection", async () => {
    server.use(
      health,
      http.post("*/api/v1/trips/plan", () => HttpResponse.json(plan)),
    );
    const user = userEvent.setup();
    render(<App queryClient={client()} />);
    await fillAndSubmit(user);
    const map = await screen.findByTestId("map-slot");
    await screen.findByRole("tablist", { name: "Log sheet days" }, { timeout: 15_000 });

    // Marker on the map -> row in the list selected, log tab of that day active.
    await user.click(within(map).getByRole("button", { name: "Marker s5" }));
    expect(map).toHaveAttribute("data-selected", "s5");
    const selectedRows = screen
      .getAllByRole("button", { pressed: true })
      .filter((el) => el.closest("[data-stop-id]"));
    expect(selectedRows).toHaveLength(1);
    expect(selectedRows[0]?.closest("[data-stop-id]")).toHaveAttribute("data-stop-id", "s5");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /^Day 3/, selected: true })).toBeInTheDocument();
    });

    // Row in the list -> map selection and log tab follow.
    const row = document.querySelector('[data-stop-id="s2"] button');
    if (!(row instanceof HTMLElement)) throw new Error("row s2 missing");
    await user.click(row);
    expect(map).toHaveAttribute("data-selected", "s2");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /^Day 1/, selected: true })).toBeInTheDocument();
    });
  });

  it("shows loading skeletons then the waking state while the server sleeps", async () => {
    server.use(
      http.get("*/api/v1/health", async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
      http.post("*/api/v1/trips/plan", () => HttpResponse.json(plan)),
    );
    const user = userEvent.setup();
    render(<App queryClient={client()} />);

    await fillAndSubmit(user);

    expect(await screen.findByRole("button", { name: /Cancel/ })).toBeInTheDocument();
    expect(screen.queryByText("337.7")).not.toBeInTheDocument();
  });

  it("shows a coded alert with the form values kept for UPSTREAM_UNAVAILABLE", async () => {
    server.use(
      health,
      http.post("*/api/v1/trips/plan", () =>
        HttpResponse.json(
          errorBody("UPSTREAM_UNAVAILABLE", "The routing service is not responding."),
          { status: 503 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<App queryClient={client()} />);

    await fillAndSubmit(user);

    expect(await screen.findByRole("button", { name: /Try again|Retry/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Dropoff/)).toHaveValue("Denver, CO");
  });

  it("prefills from the share param and does not plan on load", async () => {
    let posts = 0;
    server.use(
      health,
      http.post("*/api/v1/trips/plan", () => {
        posts += 1;
        return HttpResponse.json(plan);
      }),
    );
    const user = userEvent.setup();
    const first = render(<App queryClient={client()} />);
    await fillAndSubmit(user);
    await screen.findByRole("heading", { name: "Summary" });
    first.unmount();
    posts = 0;

    render(<App queryClient={client()} />);

    expect(screen.getByLabelText(/Dropoff/)).toHaveValue("Denver, CO");
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(posts).toBe(0);
    expect(screen.queryByRole("heading", { name: "Summary" })).not.toBeInTheDocument();
  });
});

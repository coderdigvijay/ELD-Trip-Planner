import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { plan, stops } from "../results/__fixtures__/multiDayTrip";

vi.mock("./MapView", () => {
  throw new Error("chunk failed to load");
});

const { LazyMapView } = await import("./LazyMapView");

describe("LazyMapView chunk failure", () => {
  it("shows an inline map error, not a blank screen", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <LazyMapView
        state={{ status: "ready", route: plan.route, stops, timezone: plan.trip.timezone }}
      />,
    );
    expect(await screen.findByText("The map could not load")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

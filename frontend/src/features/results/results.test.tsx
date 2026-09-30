import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { days, LONG_LABEL, must, plan, stops, timeline } from "./__fixtures__/multiDayTrip";
import { createHoverStore } from "./hoverStore";
import { logFocusForStop } from "./selection";
import { StopTimeline, type StopTimelineState } from "./StopTimeline";
import { formatClock, formatDuration, formatSpan } from "./time";
import { buildDayGroups } from "./timelineModel";
import { TripSummary } from "./TripSummary";
import { warningCopy } from "./warnings";

const timezone = plan.trip.timezone;
const readyTimeline: StopTimelineState = {
  status: "ready",
  stops,
  timeline,
  days,
  timezone,
  counts: plan.summary.counts,
};

describe("time formatting in the frozen trip offset", () => {
  it("shows the local part of the ISO string on the DST fall-back date, whatever the runner zone", () => {
    // 06:00-04:00 is 05:00 in New York on 2026-11-01 (EST). The trip stays at -04:00.
    expect(formatClock("2026-11-01T06:00:00-04:00", timezone)).toBe("06:00");
    expect(formatClock("2026-11-01T01:30:00-04:00", timezone)).toBe("01:30");
    expect(formatClock("2026-11-02T02:00:00-04:00", timezone)).toBe("02:00");
  });

  it("formats durations and spans per DESIGN_SYSTEM 8", () => {
    expect(formatDuration(0.5)).toBe("30 m");
    expect(formatDuration(7.75)).toBe("7 h 45 m");
    expect(formatDuration(4)).toBe("4 h");
    expect(formatSpan(55.5)).toBe("2 d 7 h 30 m");
    expect(formatSpan(8.5)).toBe("8 h 30 m");
  });
});

describe("timeline model", () => {
  const groups = buildDayGroups(stops, timeline, timezone, days);

  it("groups by arrival date and repeats a stop past midnight as a cont. row", () => {
    expect(groups.map((g) => g.key)).toEqual(["2026-10-31", "2026-11-01", "2026-11-02"]);
    const day2 = groups[1]?.rows.map((r) => `${r.time} ${r.stop.id}${r.cont ? " cont" : ""}`);
    expect(day2).toEqual(["00:00 s2 cont", "06:00 s3", "18:00 s4"]);
    expect(groups[1]?.rows[0]?.durationH).toBe(0.25);
  });

  it("attaches the driving leg that ends at each stop", () => {
    const s2 = groups[0]?.rows.find((r) => r.stop.id === "s2");
    expect(s2?.drive).toEqual({ hours: 2.75, miles: expect.closeTo(152.3, 5) as number });
  });

  it("locates a stop on its sheet for the log", () => {
    const s3 = stops.find((s) => s.id === "s3");
    expect(s3 && logFocusForStop(s3, days, timezone)).toEqual({ sheetIndex: 2, minute: 360 });
  });
});

describe("StopTimeline", () => {
  it("renders the zone once, a heading per day and an ordered list of rows", () => {
    render(<StopTimeline state={readyTimeline} />);
    expect(screen.getByText("All times EDT (UTC-04:00), home terminal time")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Day 1 Sat, Oct 31",
      "Day 2 Sun, Nov 1",
      "Day 3 Mon, Nov 2",
    ]);
    expect(screen.getAllByRole("list")).toHaveLength(3);
    expect(screen.getByRole("button", { name: /^06:00.*10-hr rest/ })).toBeInTheDocument();
    expect(screen.getByText("10-hr rest: 11 hr driving limit reached")).toBeInTheDocument();
    expect(screen.getByText(/Drive 2 h 45 m . 152 mi/)).toBeInTheDocument();
  });

  it("marks the midnight continuation and adds an OFF badge for release from duty", () => {
    render(<StopTimeline state={readyTimeline} />);
    expect(screen.getByRole("button", { name: /^00:00.*Pickup \(cont\.\)/ })).toBeInTheDocument();
    const released = screen.getByRole("button", { name: /Released from duty/ });
    expect(within(released).getByText("Off duty")).toBeInTheDocument();
  });

  it("keeps a long place name whole for assistive tech, clamped visually", () => {
    render(<StopTimeline state={readyTimeline} />);
    const row = screen.getByRole("button", { name: new RegExp(LONG_LABEL.slice(0, 30)) });
    expect(row).toHaveAccessibleName(expect.stringContaining(LONG_LABEL));
    expect(row.querySelector(".line-clamp-2")?.textContent).toContain(LONG_LABEL);
  });

  it("selects on click and on Enter, reports the sheet, and clears on Escape", async () => {
    const user = userEvent.setup();
    const onSelectStop = vi.fn();
    const onSelectDay = vi.fn();
    const { rerender } = render(
      <StopTimeline
        state={readyTimeline}
        selectedStopId={null}
        onSelectStop={onSelectStop}
        onSelectDay={onSelectDay}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Fuel, near Hagerstown/ }));
    expect(onSelectStop).toHaveBeenLastCalledWith("s4");
    expect(onSelectDay).toHaveBeenLastCalledWith(2);

    screen.getByRole("button", { name: /Dropoff, Newark/ }).focus();
    await user.keyboard("{Enter}");
    expect(onSelectStop).toHaveBeenLastCalledWith("s5");
    expect(onSelectDay).toHaveBeenLastCalledWith(3);

    rerender(
      <StopTimeline
        state={readyTimeline}
        selectedStopId="s5"
        onSelectStop={onSelectStop}
        onSelectDay={onSelectDay}
      />,
    );
    const selected = screen.getByRole("button", { name: /Dropoff, Newark/ });
    expect(selected).toHaveAttribute("aria-pressed", "true");
    await user.keyboard("{Escape}");
    expect(onSelectStop).toHaveBeenLastCalledWith(null);
  });

  it("offers a View log button per day", async () => {
    const user = userEvent.setup();
    const onSelectDay = vi.fn();
    render(<StopTimeline state={readyTimeline} onSelectDay={onSelectDay} />);
    await user.click(screen.getByRole("button", { name: "View log for day 3" }));
    expect(onSelectDay).toHaveBeenCalledWith(3);
  });

  it("says no stops are needed when the counts are all zero", () => {
    render(
      <StopTimeline
        state={{
          ...readyTimeline,
          stops: stops.slice(0, 1),
          counts: { fuel: 0, break: 0, rest: 0, restart: 0 },
        }}
      />,
    );
    expect(screen.getByText("No stops needed. The trip fits in one shift.")).toBeInTheDocument();
  });

  it("shows skeleton rows while loading and nothing for empty or error", () => {
    const { container, rerender } = render(<StopTimeline state={{ status: "loading" }} />);
    expect(screen.getByRole("region", { name: "Stops", busy: true })).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(8);
    rerender(<StopTimeline state={{ status: "empty" }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<StopTimeline state={{ status: "error" }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("bounds the card from lg and makes the list a labelled, focusable scroll region", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    try {
      render(<StopTimeline state={readyTimeline} />);
      const stopsCard = screen.getByRole("region", { name: "Stops" });
      expect(stopsCard).toHaveClass("lg:max-h-120", "xl:relative");
      const scroller = screen.getByRole("region", { name: "Trip timeline" });
      expect(scroller).toHaveAttribute("tabindex", "0");
      expect(scroller).toHaveClass("lg:overflow-y-auto");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("does not add a tab stop below lg, where the list flows in the page", () => {
    render(<StopTimeline state={readyTimeline} />);
    expect(screen.queryByRole("region", { name: "Trip timeline" })).not.toBeInTheDocument();
  });

  it("says approximate locations once under the heading when the plan warns", () => {
    const { rerender } = render(<StopTimeline state={readyTimeline} />);
    expect(screen.queryByText("Some stop locations are approximate.")).not.toBeInTheDocument();
    rerender(<StopTimeline state={{ ...readyTimeline, approximate: true }} />);
    expect(screen.getByText("Some stop locations are approximate.")).toBeInTheDocument();
  });

  it("highlights a row while the shared hover store names its stop, and only that row", () => {
    const hover = createHoverStore();
    render(<StopTimeline state={readyTimeline} hover={hover} />);
    const first = must(stops[0]);
    const row = screen.getByRole("button", {
      name: new RegExp(`^${first.arrive_at.slice(11, 16)}`),
    });
    expect(row).not.toHaveClass("bg-surface-sunk");
    act(() => {
      hover.set(first.id);
    });
    expect(row).toHaveClass("bg-surface-sunk");
    expect(
      screen.getAllByRole("button").filter((b) => b.classList.contains("bg-surface-sunk")),
    ).toHaveLength(1);
    act(() => {
      hover.set(null);
    });
    expect(row).not.toHaveClass("bg-surface-sunk");
  });

  it("handles 60+ rows without dropping any", () => {
    const many = Array.from({ length: 64 }, (_, i) => ({
      ...must(stops[3]),
      id: `m${i}`,
      arrive_at: "2026-11-01T18:00:00-04:00",
    }));
    render(<StopTimeline state={{ ...readyTimeline, stops: many }} />);
    expect(screen.getAllByRole("button", { name: /Fuel/ })).toHaveLength(64);
  });
});

describe("TripSummary", () => {
  const ready = { status: "ready", summary: plan.summary, trip: plan.trip } as const;

  it("prints the API figures in contract order and units", () => {
    render(<TripSummary state={ready} />);
    const figures = screen
      .getAllByRole("term")
      .map((t) => [t.textContent, t.nextElementSibling?.textContent]);
    expect(figures).toEqual([
      ["Distance", "1,204 mi"],
      ["Driving", "16 h 30 m"],
      ["Trip time", "2 d 6 h"],
      ["Daily logs", "3"],
      ["Cycle used at release", "29.5 of 70 h"],
    ]);
    expect(screen.getByText(/1 fuel, 1 10-hr rest/)).toBeInTheDocument();
  });

  it("shrinks figures for very long trips instead of truncating", () => {
    render(
      <TripSummary state={{ ...ready, summary: { ...plan.summary, total_distance_mi: 5210.4 } }} />,
    );
    expect(screen.getByText("5,210 mi").className).toContain("text-lg");
  });

  it("maps every known warning code to plain words and keeps unknown ones", () => {
    const warnings = [
      { code: "CAR_PROFILE_USED", message: "raw" },
      { code: "LABELS_APPROXIMATED", message: "raw" },
      { code: "CYCLE_RESTART_AT_START", message: "raw" },
      { code: "SOMETHING_NEW", message: "The server said this." },
    ];
    render(<TripSummary state={{ ...ready, trip: { ...plan.trip, warnings } }} />);
    expect(screen.getByText("Car route used")).toBeInTheDocument();
    expect(screen.getByText("Car route")).toBeInTheDocument();
    // LABELS_APPROXIMATED lives under the Stops heading, not in the Summary.
    expect(screen.queryByText("Some stop locations are approximate")).not.toBeInTheDocument();
    expect(screen.getByText("The trip starts with a 34-hour restart")).toBeInTheDocument();
    expect(screen.getByText("The server said this.")).toBeInTheDocument();
    expect(screen.queryByText("raw")).not.toBeInTheDocument();
    expect(warningCopy(must(warnings[0])).body).toMatch(/car route/);
  });

  it("shows the stale line only when asked", () => {
    const { rerender } = render(<TripSummary state={ready} />);
    expect(screen.queryByText(/Trip inputs changed/)).not.toBeInTheDocument();
    rerender(<TripSummary state={ready} stale />);
    expect(
      screen.getByText("Trip inputs changed. Plan trip again to update these results."),
    ).toBeInTheDocument();
  });

  it("opens the assumptions dialog with the API list and returns focus on Escape", async () => {
    const user = userEvent.setup();
    render(<TripSummary state={ready} />);
    const trigger = screen.getByRole("button", { name: "Assumptions" });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", { name: "Assumptions" });
    expect(within(dialog).getByText("A17")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("reserves the figure box while loading and renders nothing for empty or error", () => {
    const { container, rerender } = render(<TripSummary state={{ status: "loading" }} />);
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(11);
    expect(container.querySelector(".min-h-19\\.5")).not.toBeNull();
    rerender(<TripSummary state={{ status: "empty" }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<TripSummary state={{ status: "error" }} />);
    expect(container).toBeEmptyDOMElement();
  });
});

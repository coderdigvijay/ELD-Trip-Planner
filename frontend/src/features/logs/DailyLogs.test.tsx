import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { shortTripHeader } from "./__fixtures__/apiExamples";
import { johnDoeDay, johnDoeHeader, johnDoeTimezone } from "./__fixtures__/johnDoe";
import { longHaulDays } from "./__fixtures__/longHaul";
import { DailyLogs, type DailyLogsState } from "./DailyLogs";
import type { LogDay } from "./types";

const ready = (days: readonly LogDay[], header = shortTripHeader): DailyLogsState => ({
  status: "ready",
  days,
  header,
  sheetCount: days.length,
  timezone: johnDoeTimezone,
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
});

describe("four states", () => {
  it("loading: a status region and no sheet", () => {
    render(<DailyLogs state={{ status: "loading" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading log sheets");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("empty: the caption and a decorative blank form", () => {
    const { container } = render(<DailyLogs state={{ status: "empty" }} />);
    expect(
      screen.getByText("Log sheets appear here, one per day of the trip."),
    ).toBeInTheDocument();
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveClass("opacity-50");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("error: a message and a working retry", async () => {
    const onRetry = vi.fn();
    render(
      <DailyLogs state={{ status: "error", message: "The server is unavailable.", onRetry }} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("The server is unavailable.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("overflow: eight days scroll in the tab list and every tab is reachable", () => {
    render(<DailyLogs state={ready(longHaulDays(8))} />);
    expect(screen.getAllByRole("tab")).toHaveLength(8);
    expect(screen.getByRole("tab", { name: "Day 8 · Mon 11/09" })).toBeInTheDocument();
  });
});

describe("day tabs", () => {
  it("names tabs by their visible text and shows the active sheet", () => {
    render(<DailyLogs state={ready([johnDoeDay], johnDoeHeader)} />);
    const tab = screen.getByRole("tab", { name: "Day 1 · Fri 04/09" });
    expect(tab).not.toHaveAttribute("aria-label");
    expect(tab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("img", { name: /sheet 1 of 1/ })).toBeInTheDocument();
  });

  it("describes the sheet with the visible summary line", () => {
    render(<DailyLogs state={ready([johnDoeDay], johnDoeHeader)} />);
    const svg = screen.getByRole("img");
    const summary = document.getElementById(
      svg.getAttribute("aria-describedby")?.split(" ")[0] ?? "",
    );
    expect(summary).toBeVisible();
    expect(summary).toHaveTextContent(
      "Off 10:00 · Sleeper 1:45 · Driving 7:45 · On duty 4:30 · Total 24:00",
    );
  });

  it("switches day with ArrowRight, updates ?day= and mounts only the active sheet", async () => {
    const user = userEvent.setup();
    render(<DailyLogs state={ready(longHaulDays(4))} />);
    expect(screen.getAllByRole("img")).toHaveLength(1);
    await user.tab();
    expect(screen.getByRole("tab", { name: /^Day 1/ })).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /^Day 2/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /^Day 2/ })).toHaveFocus();
    expect(window.location.search).toBe("?day=2");
    expect(screen.getByRole("img", { name: /sheet 2 of 4/ })).toBeInTheDocument();
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: /^Day 4/ })).toHaveAttribute("aria-selected", "true");
  });

  it("reads the day from the URL and repairs an out-of-range value", () => {
    window.history.replaceState(null, "", "/?day=3");
    const { unmount } = render(<DailyLogs state={ready(longHaulDays(4))} />);
    expect(screen.getByRole("tab", { name: /^Day 3/ })).toHaveAttribute("aria-selected", "true");
    unmount();
    window.history.replaceState(null, "", "/?day=99");
    render(<DailyLogs state={ready(longHaulDays(4))} />);
    expect(screen.getByRole("tab", { name: /^Day 1/ })).toHaveAttribute("aria-selected", "true");
    expect(window.location.search).toBe("?day=1");
  });

  it("returns to day 1 for a new plan", () => {
    window.history.replaceState(null, "", "/?day=3");
    const { rerender } = render(<DailyLogs state={ready(longHaulDays(4))} />);
    rerender(<DailyLogs state={ready(longHaulDays(5))} />);
    expect(screen.getByRole("tab", { name: /^Day 1/ })).toHaveAttribute("aria-selected", "true");
    expect(window.location.search).toBe("?day=1");
  });
});

describe("Show table (test 20)", () => {
  it("is closed by default, and lists 13 segments, 12 remarks and a total of 24", () => {
    render(<DailyLogs state={ready([johnDoeDay], johnDoeHeader)} />);
    const details = screen.getByText("Show table").closest("details");
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText("Show table")).toBeVisible();
    const [segments, remarks, totals] = within(details as HTMLElement).getAllByRole("table");
    expect(within(segments as HTMLElement).getAllByRole("row")).toHaveLength(14);
    expect(within(remarks as HTMLElement).getAllByRole("row")).toHaveLength(13);
    const totalRow = within(totals as HTMLElement)
      .getAllByRole("row")
      .at(-1);
    expect(totalRow).toHaveTextContent("Total24");
    expect(within(segments as HTMLElement).getAllByText("Sleeper berth").length).toBeGreaterThan(0);
    expect(screen.getByText("Not applicable")).toBeInTheDocument();
  });
});

describe("per-day guard (test 21)", () => {
  it("shows the warn alert and the opened table instead of a half-drawn sheet", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const gap: LogDay = {
      ...johnDoeDay,
      segments: johnDoeDay.segments.map((s) =>
        s.start_min === 570 ? { ...s, start_min: 585 } : s,
      ),
    };
    const { container } = render(<DailyLogs state={ready([gap], johnDoeHeader)} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This day's log could not be drawn. Its duty status changes are listed below.",
    );
    expect(container.querySelector("svg[role='img']")).toBeNull();
    expect(container.querySelector("details")).toHaveAttribute("open");
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  it("rejects totals that do not add up to 24", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <DailyLogs
        state={ready([{ ...johnDoeDay, totals: { ...johnDoeDay.totals, off: 9 } }], johnDoeHeader)}
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    spy.mockRestore();
  });
});

describe("scroll mode (narrow container)", () => {
  function stubWidth(width: number) {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(private readonly cb: ResizeObserverCallback) {}
        observe(el: Element) {
          this.cb([{ target: el, contentRect: { width } } as ResizeObserverEntry], this);
        }
        unobserve() {}
        disconnect() {}
      },
    );
  }

  it("uses a focusable, labelled scroll region with a Fit width toggle", async () => {
    stubWidth(360);
    render(<DailyLogs state={ready([johnDoeDay], johnDoeHeader)} />);
    const region = screen.getByRole("region", { name: "Log sheet, scroll horizontally" });
    expect(region).toHaveAttribute("tabindex", "0");
    // The tab panel itself is not a tab stop (the region is the only one).
    expect(screen.getByRole("tabpanel")).toHaveAttribute("tabindex", "-1");
    // Sizing is a CSS container query (checked in a real browser by e2e/logs.spec.ts).
    expect(screen.getByTestId("sheet-frame")).toHaveAttribute("data-fit", "false");
    expect(screen.getByTestId("sheet-frame")).toHaveClass("w-[960px]");
    expect(
      screen.getByText("Scroll sideways to read the full sheet, or print it."),
    ).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "Fit width" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Actual size" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("sheet-frame")).toHaveAttribute("data-fit", "true");
    expect(screen.queryByRole("region", { name: "Log sheet, scroll horizontally" })).toBeNull();
  });

  it("is fluid, with no scroll region, on a wide container", () => {
    stubWidth(1200);
    render(<DailyLogs state={ready([johnDoeDay], johnDoeHeader)} />);
    expect(screen.queryByRole("region", { name: "Log sheet, scroll horizontally" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Fit width" })).toBeNull();
    expect(screen.getByTestId("sheet-frame")).toHaveClass("@min-[900px]:max-w-[1200px]");
  });
});

describe("print", () => {
  it("mounts every sheet on Print logs and calls window.print", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<DailyLogs state={ready(longHaulDays(3))} />);
    await userEvent.click(screen.getByRole("button", { name: "Print logs" }));
    const all = await screen.findByTestId("print-all-logs");
    expect(all.querySelectorAll(".log-sheet-page")).toHaveLength(3);
    await vi.waitFor(() => {
      expect(print).toHaveBeenCalledOnce();
    });
    window.dispatchEvent(new Event("afterprint"));
    await vi.waitFor(() => {
      expect(screen.queryByTestId("print-all-logs")).toBeNull();
    });
    print.mockRestore();
  });

  it("shows the full shipper and commodity in the table view", () => {
    render(<DailyLogs state={ready([johnDoeDay])} />);
    expect(screen.getByText(shortTripHeader.shipper_commodity)).toBeInTheDocument();
  });
});

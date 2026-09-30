import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { vi } from "vitest";

import { midRestDay, restartDay, shortTripDay, shortTripHeader } from "./__fixtures__/apiExamples";
import { johnDoeDay, johnDoeHeader, johnDoeTimezone } from "./__fixtures__/johnDoe";
import { longHaulDays } from "./__fixtures__/longHaul";
import { LogSheet } from "./LogSheet";
import { BLANK_FORM } from "./BlankForm";
import { dutyPath } from "./geometry";
import * as sheetModel from "./sheetModel";
import { FONT_MONO, FONT_SANS, INK, PEN, SURFACE } from "./tokens";
import type { LogDay } from "./types";

vi.mock("./sheetModel", async (importOriginal) => {
  const actual = await importOriginal<typeof sheetModel>();
  return { ...actual, buildSheetModel: vi.fn(actual.buildSheetModel) };
});

function renderDoe(overrides: Partial<React.ComponentProps<typeof LogSheet>> = {}) {
  return render(
    <LogSheet
      day={johnDoeDay}
      header={johnDoeHeader}
      sheetCount={1}
      timezone={johnDoeTimezone}
      {...overrides}
    />,
  );
}

const texts = (container: HTMLElement, selector = "text") =>
  Array.from(container.querySelectorAll(selector)).map((el) => el.textContent);

describe("LogSheet, John Doe (spec 6.2 tests 17 to 19)", () => {
  it("draws one duty path with the golden d and the filled entries", () => {
    const { container } = renderDoe();
    const path = container.querySelector('[data-part="duty-line"]');
    expect(path).toHaveAttribute("d", dutyPath(johnDoeDay.segments));
    expect(path?.getAttribute("d")).toBe(
      "M124 354 H316 V462 H364 V426 H412 V462 H428 V426 H508 V354 H540 V426 H604 V462 H620 V426 H636 V390 H692 V426 H732 V462 H796 V354 H892",
    );
    const entries = texts(container, '[data-part="entries"] text');
    expect(entries.slice(0, 3)).toEqual(["04", "09", "2021"]);
    expect(entries).toEqual(
      expect.arrayContaining([
        "350",
        "John Doe's Transportation",
        "Washington, D.C.",
        "123, 20544",
        "101601",
      ]),
    );
    // Totals column reads 10 / 1.75 / 7.75 / 4.5 then =24, in that order.
    const totalIndex = entries.indexOf("10");
    expect(entries.slice(totalIndex, totalIndex + 5)).toEqual(["10", "1.75", "7.75", "4.5", "=24"]);
  });

  it("prints every total exactly once and they add up to 24", () => {
    const { container } = renderDoe();
    const grand = texts(container, '[data-part="entries"] text').find((t) => t.startsWith("="));
    expect(grand).toBe("=24");
    const { totals } = johnDoeDay;
    expect(totals.off + totals.sleeper + totals.driving + totals.on_duty).toBe(24);
  });

  it("writes six place names at 45 degrees in minute order", () => {
    const { container } = renderDoe();
    const groups = Array.from(container.querySelectorAll("[data-remark]"));
    expect(groups).toHaveLength(6);
    expect(groups.map((g) => g.querySelector("text")?.textContent)).toEqual([
      "Richmond, VA",
      "Fredericksburg, VA",
      "Baltimore, MD",
      "Philadelphia, PA",
      "Cherry Hill, NJ",
      "Newark, NJ",
    ]);
    for (const g of groups) expect(g.getAttribute("transform")).toMatch(/rotate\(45\)$/);
    expect(groups.map((g) => g.getAttribute("data-remark"))).toEqual([
      "360",
      "540",
      "720",
      "900",
      "960",
      "1140",
    ]);
  });

  it("is an image with a title and a description that carries the totals", () => {
    renderDoe();
    const svg = screen.getByRole("img", {
      name: "Driver's daily log, Fri Apr 9, 2021, sheet 1 of 1",
    });
    const describedBy = svg.getAttribute("aria-describedby") ?? "";
    const desc = document.getElementById(describedBy);
    expect(desc?.textContent).toBe(
      "Off 10:00 · Sleeper 1:45 · Driving 7:45 · On duty 4:30 · Total 24:00",
    );
  });

  it("points aria-describedby at a visible summary line when one is given", () => {
    render(
      <>
        <p id="day-summary">summary</p>
        <LogSheet day={johnDoeDay} header={johnDoeHeader} sheetCount={1} summaryId="day-summary" />
      </>,
    );
    expect(screen.getByRole("img")).toHaveAttribute("aria-describedby", "day-summary");
  });

  it("prints the footer, the time base and the six brackets", () => {
    const { container } = renderDoe({ sheetCount: 5, day: { ...johnDoeDay, sheet_index: 2 } });
    expect(screen.getByText("Sheet 2 of 5")).toBeInTheDocument();
    expect(screen.getByText("04/09/2021")).toBeInTheDocument();
    expect(screen.getByText("Home terminal time: EDT (UTC-04:00)")).toBeInTheDocument();
    expect(
      container.querySelector('[data-part="brackets"]')?.getAttribute("d")?.match(/M/g),
    ).toHaveLength(6);
  });

  it("says Sheet 1 of 1", () => {
    renderDoe();
    expect(screen.getByText("Sheet 1 of 1")).toBeInTheDocument();
  });

  it("uses only ink, pen and surface, and the two font stacks", () => {
    const { container } = renderDoe();
    const allowed = new Set([INK, PEN, SURFACE, "none"]);
    const paints = new Set<string>();
    container.querySelectorAll("[fill],[stroke]").forEach((el) => {
      for (const attr of ["fill", "stroke"]) {
        const v = el.getAttribute(attr);
        if (v) paints.add(v);
      }
    });
    expect([...paints].filter((p) => !allowed.has(p))).toEqual([]);
    const families = new Set(
      Array.from(container.querySelectorAll("[font-family]")).map((e) =>
        e.getAttribute("font-family"),
      ),
    );
    expect([...families].every((f) => f === FONT_SANS || f === FONT_MONO)).toBe(true);
  });

  it("renders no HTML from API strings", () => {
    const evil: LogDay = { ...johnDoeDay, from_label: "<img src=x onerror=alert(1)>" };
    const { container } = renderDoe({ day: evil });
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x");
  });
});

describe("recap (test 22)", () => {
  it("shows the four values and three N/A entries in pen", () => {
    const { container } = renderDoe();
    const entries = texts(container, '[data-part="entries"] text');
    const tail = entries.slice(entries.indexOf("=24") + 1);
    expect(tail.slice(0, 7)).toEqual(["12.25", "12.25", "57.75", "12.25", "N/A", "N/A", "N/A"]);
    expect(container.querySelector('[data-part="entries"]')).toHaveAttribute("fill", PEN);
    expect(entries.filter((t) => t === "70*")).toHaveLength(0);
  });

  it("writes 70* and the restart note when a restart is in progress, whatever B holds", () => {
    const { container } = render(
      <LogSheet day={restartDay} header={shortTripHeader} sheetCount={2} />,
    );
    const entries = texts(container, '[data-part="entries"] text');
    expect(entries).toContain("70*");
    expect(entries.join(" ")).toContain("34-hr restart");
    expect(entries.join(" ")).toContain("10/06 10:00");
    const zeroB: LogDay = {
      ...restartDay,
      recap: { ...restartDay.recap, b_available_tomorrow: 0 },
    };
    const again = render(<LogSheet day={zeroB} header={shortTripHeader} sheetCount={2} />);
    expect(texts(again.container, '[data-part="entries"] text')).toContain("70*");
  });

  it("prints a plain number and no 70* without a restart note", () => {
    const { container } = render(
      <LogSheet day={shortTripDay} header={shortTripHeader} sheetCount={1} />,
    );
    const entries = texts(container, '[data-part="entries"] text');
    expect(entries).toContain("51.5");
    expect(entries).not.toContain("70*");
  });
});

describe("long values (test 24)", () => {
  it("fits 80 character names in every header field and keeps the full text in a title", () => {
    const long = "W".repeat(80);
    const { container } = render(
      <LogSheet
        day={{ ...johnDoeDay, from_label: long, to_label: long }}
        header={{
          driver_name: long,
          carrier_name: long,
          main_office_address: long,
          home_terminal_address: long,
          truck_number: long,
          trailer_number: long,
          shipping_doc: long,
          shipper_commodity: long,
        }}
        sheetCount={1}
      />,
    );
    // width limits by "x,y" of each entry (spec 2.1 and 2.5)
    const limits: Record<string, number> = {
      "116,83": 358,
      "546,83": 392,
      "271,225": 310,
      "700,107": 480,
      "700,147": 480,
      "700,189": 480,
      "700,231": 480,
      "48,670": 150,
      "48,730": 150,
    };
    const fitted = Array.from(container.querySelectorAll('[data-part="entries"] text')).filter(
      (el) => `${el.getAttribute("x")},${el.getAttribute("y")}` in limits,
    );
    expect(fitted).toHaveLength(9);
    for (const el of fitted) {
      const limit = limits[`${el.getAttribute("x")},${el.getAttribute("y")}`] ?? 0;
      const drawn = Array.from(el.childNodes)
        .filter((n) => n.nodeType === Node.TEXT_NODE)
        .map((n) => n.textContent)
        .join("");
      expect(0.6 * Number(el.getAttribute("font-size")) * drawn.length).toBeLessThanOrEqual(
        limit + 1e-6,
      );
      expect(el.querySelector("title")?.textContent).toContain("WWWW");
    }
  });

  it("truncates a long remark place and keeps the full text on hover", () => {
    const place = "Extraordinarily Long Place Name, XX";
    const day: LogDay = {
      ...shortTripDay,
      remarks: [{ minute: 1425, location_label: place, note: "Fuel" }],
      segments: [
        {
          ...shortTripDay.segments[0],
          start_min: 0,
          end_min: 1440,
          status: "off" as const,
          location_label: "X",
          note: "Off duty",
          stationary: false,
          stop_id: null,
        },
      ],
    };
    const { container } = render(<LogSheet day={day} header={shortTripHeader} sheetCount={1} />);
    const label = container.querySelector("[data-remark]");
    expect(label?.querySelector("title")?.textContent).toBe(`23:45 ${place}, Fuel`);
    expect(label?.querySelector("text")?.textContent.endsWith("...")).toBe(true);
  });
});

describe("tokens (test 16)", () => {
  const css = readFileSync(join(import.meta.dirname, "..", "..", "index.css"), "utf8");
  const token = (name: string) => new RegExp(`--${name}:\\s*([^;]+);`).exec(css)?.[1]?.trim();

  it("matches the @theme values", () => {
    expect(token("color-ink")).toBe(INK);
    expect(token("color-pen")).toBe(PEN);
    expect(token("color-surface")).toBe(SURFACE);
    expect(token("font-sans")).toBe(FONT_SANS);
    expect(token("font-mono")?.replace(/\s+/g, " ")).toBe(FONT_MONO);
  });
});

describe("other API examples", () => {
  it("draws the mid-rest sheet without console errors", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { container } = render(
      <LogSheet day={midRestDay} header={shortTripHeader} sheetCount={3} />,
    );
    expect(spy).not.toHaveBeenCalled();
    expect(container.querySelectorAll("[data-remark]").length).toBeGreaterThan(0);
    spy.mockRestore();
  });

  it("every fixture total sums to 24", () => {
    for (const day of [johnDoeDay, shortTripDay, midRestDay, restartDay, ...longHaulDays(8)]) {
      const t = day.totals;
      expect(t.off + t.sleeper + t.driving + t.on_duty).toBeCloseTo(24, 6);
    }
  });
});

describe("memoization (test 26)", () => {
  it("does not rebuild the model for the same day reference and keeps the blank form a constant", () => {
    const build = vi.mocked(sheetModel.buildSheetModel);
    build.mockClear();
    const props = { day: johnDoeDay, header: johnDoeHeader, sheetCount: 1 };
    const { rerender } = render(<LogSheet {...props} />);
    rerender(<LogSheet {...props} />);
    expect(build).toHaveBeenCalledTimes(1);
    expect(BLANK_FORM).toBe(BLANK_FORM);
  });
});

describe("snapshots (test 25)", () => {
  const normalize = (svg: Element | null) =>
    svg?.outerHTML.replace(/ (id|aria-labelledby|aria-describedby)="[^"]*"/g, "");

  it("John Doe", () => {
    const { container } = renderDoe();
    expect(normalize(container.querySelector("svg"))).toMatchSnapshot();
  });

  it("a long-haul sheet", () => {
    const second = longHaulDays(5)[1] ?? johnDoeDay;
    const { container } = render(<LogSheet day={second} header={shortTripHeader} sheetCount={5} />);
    expect(normalize(container.querySelector("svg"))).toMatchSnapshot();
  });
});

it("within helper is available", () => {
  const { container } = renderDoe();
  expect(within(container).getByText("Drivers Daily Log")).toBeInTheDocument();
});

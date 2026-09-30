import { johnDoeDay } from "./__fixtures__/johnDoe";
import { longHaulDays } from "./__fixtures__/longHaul";
import { midRestDay, restartDay, shortTripDay } from "./__fixtures__/apiExamples";
import {
  HOUR_PATH,
  TICK_PATH,
  bracketPath,
  brackets,
  dutyPath,
  segmentIssues,
  x,
  y,
} from "./geometry";
import type { LogSegment } from "./types";

const seg = (start_min: number, end_min: number, status: LogSegment["status"]): LogSegment => ({
  start_min,
  end_min,
  status,
  location_label: "",
  note: "",
  stationary: false,
  stop_id: null,
});

describe("x and y mapping", () => {
  it("maps the reference minutes", () => {
    expect([0, 15, 360, 720, 1440].map(x)).toEqual([124, 132, 316, 508, 892]);
  });

  it("is an integer for every multiple of 15", () => {
    for (let m = 0; m <= 1440; m += 15) expect(Number.isInteger(x(m))).toBe(true);
  });

  it("maps statuses to row centerlines", () => {
    expect([y("off"), y("sleeper"), y("driving"), y("on_duty")]).toEqual([354, 390, 426, 462]);
  });
});

describe("dutyPath", () => {
  it("draws the John Doe line with 13 runs and 12 connectors", () => {
    const d = dutyPath(johnDoeDay.segments);
    expect(d).toBe(
      "M124 354 H316 V462 H364 V426 H412 V462 H428 V426 H508 V354 H540 V426 H604 V462 H620 V426 H636 V390 H692 V426 H732 V462 H796 V354 H892",
    );
    expect(d.match(/V/g)).toHaveLength(12);
    expect(d.match(/H/g)).toHaveLength(13);
  });

  it("omits the connector between same-status neighbours", () => {
    expect(dutyPath([seg(0, 600, "off"), seg(600, 1440, "off")])).toBe("M124 354 H444 H892");
    expect(dutyPath([seg(0, 1440, "off")])).toBe("M124 354 H892");
  });

  it("starts a new subpath on a gap and draws no connector", () => {
    const d = dutyPath([seg(0, 600, "off"), seg(615, 1440, "driving")]);
    expect(d).toBe("M124 354 H444 M452 426 H892");
    expect(d).not.toContain("V");
  });
});

describe("segmentIssues", () => {
  it("accepts every fixture", () => {
    for (const day of [johnDoeDay, shortTripDay, midRestDay, restartDay, ...longHaulDays(8)]) {
      expect(segmentIssues(day.segments)).toEqual([]);
    }
  });

  it("reports gaps, overlaps and a wrong start or end", () => {
    expect(
      segmentIssues([seg(0, 600, "off"), seg(615, 1440, "driving")]).map((i) => i.kind),
    ).toEqual(["gap"]);
    expect(
      segmentIssues([seg(0, 600, "off"), seg(585, 1440, "driving")]).map((i) => i.kind),
    ).toEqual(["overlap"]);
    expect(segmentIssues([seg(15, 1440, "off")]).map((i) => i.kind)).toEqual(["start"]);
    expect(segmentIssues([seg(0, 1425, "off")]).map((i) => i.kind)).toEqual(["end"]);
    expect(segmentIssues([]).map((i) => i.kind)).toEqual(["empty"]);
  });
});

describe("brackets", () => {
  it("returns the six John Doe stops", () => {
    expect(brackets(johnDoeDay.segments).map((b) => [b.x0, b.x1])).toEqual([
      [316, 364],
      [412, 428],
      [508, 540],
      [604, 620],
      [636, 692],
      [732, 796],
    ]);
  });

  it("draws shallow U shapes, 6 units deep", () => {
    expect(bracketPath(brackets(shortTripDay.segments).slice(0, 1))).toBe(
      "M380 482 V488 H396 V482",
    );
  });
});

describe("tick paths", () => {
  it("has 23 hour lines and the expected tick count per row", () => {
    expect(HOUR_PATH.match(/M/g)).toHaveLength(23);
    // 24 half + 48 quarter per row, 4 rows
    expect(TICK_PATH.match(/M/g)).toHaveLength(4 * 72);
  });

  it("hangs ticks from the top in rows 1 and 2 and raises them from the bottom in rows 3 and 4", () => {
    // half-hour tick at 00:30 is x(30) = 140
    expect(TICK_PATH.includes("M140 336 V354")).toBe(true); // off, hangs 18
    expect(TICK_PATH.includes("M140 372 V390")).toBe(true); // sleeper
    expect(TICK_PATH.includes("M140 426 V444")).toBe(true); // driving, rises from 444
    expect(TICK_PATH.includes("M140 462 V480")).toBe(true); // on duty, rises from 480
    // quarter tick at 00:15 is x(15) = 132, length 11
    expect(TICK_PATH.includes("M132 336 V347")).toBe(true);
    expect(TICK_PATH.includes("M132 469 V480")).toBe(true);
  });
});

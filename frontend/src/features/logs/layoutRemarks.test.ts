import { johnDoeDay } from "./__fixtures__/johnDoe";
import { shortTripDay } from "./__fixtures__/apiExamples";
import { labelGap, layoutRemarks, dropPath } from "./layoutRemarks";
import type { LogRemark, LogSegment } from "./types";

const rem = (minute: number, note = "Fuel", place = "Somewhere, ST"): LogRemark => ({
  minute,
  location_label: place,
  note,
});
const stop = (
  start_min: number,
  end_min: number,
  status: LogSegment["status"],
  note: string,
  place = "Fredericksburg, VA",
): LogSegment => ({
  start_min,
  end_min,
  status,
  location_label: place,
  note,
  stationary: true,
  stop_id: `s${start_min}`,
});
const travel = (start_min: number, end_min: number): LogSegment => ({
  start_min,
  end_min,
  status: "driving",
  location_label: "Road",
  note: "Driving",
  stationary: false,
  stop_id: null,
});

const anchors = (remarks: LogRemark[], segments: LogSegment[] = []) =>
  layoutRemarks(remarks, segments).drawn.map((d) => d.ax);

describe("folding into brackets (3.4 step 0)", () => {
  it("draws the six John Doe places with no leaders and folds the six returns to driving", () => {
    const layout = layoutRemarks(johnDoeDay.remarks, johnDoeDay.segments);
    expect(layout.mode).toBe("full");
    expect(layout.drawn.map((d) => d.ax)).toEqual([340, 420, 524, 612, 664, 764]);
    expect(layout.drawn.some((d) => d.leader)).toBe(false);
    expect(layout.drawn.map((d) => d.line1)).toEqual([
      "Richmond, VA",
      "Fredericksburg, VA",
      "Baltimore, MD",
      "Philadelphia, PA",
      "Cherry Hill, NJ",
      "Newark, NJ",
    ]);
    expect(layout.folded.map((r) => r.minute)).toEqual([450, 570, 780, 930, 1065, 1260]);
  });

  it("gives the API_CONTRACT 5.3 example 3 drawn and 3 folded", () => {
    const layout = layoutRemarks(shortTripDay.remarks, shortTripDay.segments);
    expect(layout.drawn).toHaveLength(3);
    expect(layout.folded).toHaveLength(3);
  });

  it("folds nothing for a bracket that starts at minute 0 without a remark", () => {
    const layout = layoutRemarks(
      [rem(390, "Driving", "Oak Grove, MO")],
      [stop(0, 390, "sleeper", "Rest", "Oak Grove, MO"), travel(390, 1440)],
    );
    expect(layout.folded).toEqual([]);
    expect(layout.drawn).toHaveLength(1);
  });

  it("keeps back-to-back different-status stops (10a)", () => {
    const layout = layoutRemarks(
      [
        rem(540, "Fuel", "Fredericksburg, VA"),
        rem(570, "10 hr rest (sleeper berth)", "Fredericksburg, VA"),
      ],
      [
        travel(0, 540),
        stop(540, 570, "on_duty", "Fuel"),
        stop(570, 1170, "sleeper", "10 hr rest (sleeper berth)"),
        travel(1170, 1440),
      ],
    );
    expect(layout.folded).toEqual([]);
    expect(layout.drawn.map((d) => d.ax0)).toEqual([420, 588]);
    expect(layout.drawn.map((d) => d.ax)).toEqual([420, 588]);
    expect(layout.drawn.every((d) => d.line2 !== null)).toBe(true);
  });

  it("labels a same-status second bracket from its own segment (10b)", () => {
    const segments = [
      travel(0, 480),
      stop(480, 510, "on_duty", "Pre-trip inspection", "Richmond, VA"),
      stop(510, 570, "on_duty", "Pickup (loading)", "Richmond, VA"),
      travel(570, 1440),
    ];
    const layout = layoutRemarks([rem(480, "Pre-trip inspection", "Richmond, VA")], segments);
    expect(layout.drawn.map((d) => d.ax0)).toEqual([388, 412]);
    expect(layout.drawn.map((d) => d.ax)).toEqual([382, 419]);
    expect(layout.drawn.every((d) => d.leader)).toBe(true);
    expect(layout.drawn[1]?.line2).toBe("Pickup (loading)");
  });

  it("draws a same-minute API remark once, as the pickup label (10b)", () => {
    const segments = [
      travel(0, 480),
      stop(480, 510, "on_duty", "Pre-trip inspection", "Richmond, VA"),
      stop(510, 570, "on_duty", "Pickup (loading)", "Richmond, VA"),
      travel(570, 1440),
    ];
    const layout = layoutRemarks(
      [
        rem(480, "Pre-trip inspection", "Richmond, VA"),
        rem(510, "Pickup (loading)", "Richmond, VA"),
      ],
      segments,
    );
    expect(layout.drawn).toHaveLength(2);
    expect(layout.folded).toEqual([]);
    expect(layout.drawn.map((d) => d.ax)).toEqual([382, 419]);
  });
});

describe("collision layout (3.5)", () => {
  it("has the documented gaps", () => {
    expect(labelGap("full", true)).toBe(37);
    expect(labelGap("full", false)).toBe(19);
    expect(labelGap("compact", true)).toBe(17);
  });

  it("pools three close labels around their ideal centre (11)", () => {
    const layout = layoutRemarks([rem(600), rem(615), rem(630)], []);
    expect(layout.drawn.map((d) => d.ax)).toEqual([415, 452, 489]);
    expect(layout.drawn.map((d) => d.leader)).toEqual([true, false, true]);
  });

  it("cuts a long place near the right edge to 14 chars (12)", () => {
    const place = "A".repeat(28);
    const [label] = layoutRemarks([rem(1425, "Fuel", place)], []).drawn;
    expect(label?.ax).toBe(884);
    expect(label?.leader).toBe(false);
    expect(label?.line1).toHaveLength(14);
    expect(label?.line1.endsWith("...")).toBe(true);
  });

  it("clamps a cluster at the right bound (13)", () => {
    expect(anchors([rem(1395), rem(1410), rem(1425)])).toEqual([821, 858, 895]);
    expect(layoutRemarks([rem(1395), rem(1410), rem(1425)], []).drawn.every((d) => d.leader)).toBe(
      true,
    );
  });

  it("spreads a dense burst evenly (14)", () => {
    const remarks = Array.from({ length: 12 }, (_, k) => rem(600 + 15 * k));
    const layout = layoutRemarks(remarks, []);
    expect(layout.mode).toBe("full");
    expect(layout.drawn.map((d) => d.ax)).toEqual(
      Array.from({ length: 12 }, (_, k) => 285 + 37 * k),
    );
    expect(layout.drawn.every((d) => d.leader)).toBe(true);
    // leaders never cross: both ends are increasing
    const ends = layout.drawn.map((d) => [d.ax0, d.ax]);
    for (let i = 1; i < ends.length; i += 1) {
      expect(ends[i]?.[0]).toBeGreaterThan(ends[i - 1]?.[0] ?? 0);
      expect(ends[i]?.[1]).toBeGreaterThan(ends[i - 1]?.[1] ?? 0);
    }
  });

  it("switches to compact, then list mode (15)", () => {
    const many = (n: number) => Array.from({ length: n }, (_, k) => rem(k * 15));
    expect(layoutRemarks(many(20), []).mode).toBe("full");
    const compact = layoutRemarks(many(40), []);
    expect(compact.mode).toBe("compact");
    expect(compact.drawn.every((d) => d.line2 === null)).toBe(true);
    expect(layoutRemarks(many(46), []).mode).toBe("compact");
    const list = layoutRemarks(many(47), []);
    expect(list.mode).toBe("list");
    expect(list.list).toHaveLength(47);
    expect(list.list[0]).toMatchObject({ x: 220, y: 560 });
    expect(list.list[16]).toMatchObject({ y: 560 });
    expect(list.list[16]?.x).toBeGreaterThan(220);
    expect(dropPath(list)).not.toContain("L");
  });
});

// Deterministic replacement for fast-check: 500 seeded random sets (LCG), same properties as spec 6.2 test 15.
function lcg(seed: number) {
  let s = seed;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

describe("layout properties (500 random days)", () => {
  it("keeps anchors integer, ordered, in bounds, spaced and inside the sheet", () => {
    const rand = lcg(20260930);
    for (let run = 0; run < 500; run += 1) {
      const count = Math.floor(rand() * 97);
      const minutes = [
        ...new Set(Array.from({ length: count }, () => Math.floor(rand() * 96) * 15)),
      ].sort((a, b) => a - b);
      const remarks = minutes.map((m) =>
        rem(
          m,
          rand() < 0.6 ? "N".repeat(Math.floor(rand() * 31)) : "",
          "P".repeat(Math.floor(rand() * 41)),
        ),
      );
      const layout = layoutRemarks(remarks, []);
      if (layout.mode === "list") {
        expect(remarks.length).toBeGreaterThan(46);
        continue;
      }
      const { drawn } = layout;
      drawn.forEach((d, i) => {
        expect(Number.isInteger(d.ax)).toBe(true);
        expect(d.ax).toBeGreaterThanOrEqual(124);
        expect(d.ax).toBeLessThanOrEqual(895);
        expect(d.ax + (4 + 0.6 * d.size * d.line1.length) * Math.SQRT1_2).toBeLessThanOrEqual(
          954 + 1e-6,
        );
        const prev = drawn[i - 1];
        if (prev) {
          expect(d.ax - prev.ax).toBeGreaterThanOrEqual(labelGap(layout.mode, d.line2 !== null));
          expect(d.ax0).toBeGreaterThan(prev.ax0);
        }
      });
      // leaders never cross: monotone ends
      for (let i = 1; i < drawn.length; i += 1) {
        expect(drawn[i]?.ax ?? 0).toBeGreaterThan(drawn[i - 1]?.ax ?? 0);
      }
    }
  });
});

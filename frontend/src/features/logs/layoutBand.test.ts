import { describe, expect, it } from "vitest";

import { bandTextBoxes, FOOTER_Y, TIME_BASE_POS, type TextBox } from "./layout";

function intersects(a: TextBox, b: TextBox): boolean {
  return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
}

describe("recap and footer band layout", () => {
  it("has no two intersecting text boxes", () => {
    const boxes = bandTextBoxes();
    const clashes: string[] = [];
    boxes.forEach((a, i) => {
      boxes.slice(i + 1).forEach((b) => {
        if (intersects(a, b)) clashes.push(`${a.name} x ${b.name}`);
      });
    });
    expect(clashes).toEqual([]);
  });

  it("puts the time base on the footer baseline, centred", () => {
    expect(TIME_BASE_POS).toEqual({ x: 500, y: FOOTER_Y });
  });

  it("keeps every box inside the sheet", () => {
    for (const b of bandTextBoxes()) {
      expect(b.x0).toBeGreaterThanOrEqual(0);
      expect(b.x1).toBeLessThanOrEqual(1000);
      expect(b.y1).toBeLessThanOrEqual(1020);
    }
  });
});

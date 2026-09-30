import { render } from "@testing-library/react";

import { johnDoeDay, johnDoeHeader, johnDoeTimezone } from "./__fixtures__/johnDoe";
import { prepareForPdf } from "./exportLogsPdf";
import { LogSheet } from "./LogSheet";

describe("prepareForPdf", () => {
  it("leaves only the two registered families and the normal or bold styles svg2pdf can resolve", () => {
    const { container } = render(
      <LogSheet
        day={johnDoeDay}
        header={johnDoeHeader}
        sheetCount={1}
        timezone={johnDoeTimezone}
      />,
    );
    const svg = container.querySelector("svg");
    if (!svg) throw new Error("no svg");
    const clone = svg.cloneNode(true) as SVGSVGElement;
    prepareForPdf(clone);
    const families = new Set(
      Array.from(clone.querySelectorAll("[font-family]")).map((e) => e.getAttribute("font-family")),
    );
    expect([...families].sort()).toEqual(["IBM Plex Mono", "Public Sans"]);
    const weights = new Set(
      Array.from(clone.querySelectorAll("[font-weight]")).map((e) => e.getAttribute("font-weight")),
    );
    // Weight 500 (pen entries) and 600 map to bold, which is registered to Medium / SemiBold.
    expect([...weights].sort()).toEqual(["400", "bold"]);
    expect(clone.querySelector("title, desc")).toBeNull();
  });
});

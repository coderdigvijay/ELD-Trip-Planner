import { BedDouble, Fuel, Pause } from "lucide";
import type { IconNode } from "lucide";

import type { StopKind } from "./types";

/**
 * One description of every stop glyph (DESIGN_SYSTEM 6.3), drawn by two renderers: the React
 * `StopGlyph` (timeline, legend) and the string serializer used for Leaflet divIcons. Colors are
 * Tailwind classes that read the design tokens, so no hex lives here.
 */
export interface SvgNode {
  tag: string;
  attrs: Record<string, string | number>;
  text?: string;
  children?: SvgNode[];
}

export interface GlyphSpec {
  size: number;
  nodes: SvgNode[];
}

const ICON_STROKE = "stroke-surface";

function icon(node: IconNode, size: number, box: number, strokeClass: string): SvgNode {
  const offset = (box - size) / 2;
  return {
    tag: "g",
    attrs: {
      transform: `translate(${offset} ${offset}) scale(${size / 24})`,
      fill: "none",
      "stroke-width": 2,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      class: strokeClass,
    },
    children: node.map(([tag, attrs]) => ({
      tag,
      attrs: Object.fromEntries(
        Object.entries(attrs).filter((entry): entry is [string, string | number] => {
          return typeof entry[1] === "string" || typeof entry[1] === "number";
        }),
      ),
    })),
  };
}

function label(text: string, box: number, fontSize: number): SvgNode {
  return {
    tag: "text",
    text,
    attrs: {
      x: box / 2,
      y: box / 2,
      "text-anchor": "middle",
      "dominant-baseline": "central",
      "font-size": fontSize,
      "font-weight": 600,
      class: "fill-surface font-mono",
    },
  };
}

const HALO = { "stroke-linejoin": "round", "paint-order": "stroke" } as const;

function ringCircle(box: number, ringClass: string): SvgNode[] {
  const r = box / 2 - 1.5 - 1.25;
  const c = box / 2;
  return [
    {
      tag: "circle",
      attrs: { cx: c, cy: c, r, "stroke-width": 5.5, class: "fill-surface stroke-surface" },
    },
    {
      tag: "circle",
      attrs: { cx: c, cy: c, r, "stroke-width": 2.5, class: `fill-surface ${ringClass}` },
    },
  ];
}

function square(box: number, text: string): SvgNode[] {
  return [
    {
      tag: "rect",
      attrs: {
        x: 1.5,
        y: 1.5,
        width: box - 3,
        height: box - 3,
        rx: 2,
        "stroke-width": 3,
        class: "fill-stop-load stroke-surface",
        ...HALO,
      },
    },
    label(text, box, 13),
  ];
}

function hexagon(box: number): SvgNode[] {
  const c = box / 2;
  const radius = c - 1.5;
  const points = [0, 1, 2, 3, 4, 5]
    .map((i) => {
      const angle = (Math.PI / 180) * (60 * i - 90);
      return `${(c + radius * Math.cos(angle)).toFixed(2)},${(c + radius * Math.sin(angle)).toFixed(2)}`;
    })
    .join(" ");
  return [
    {
      tag: "polygon",
      attrs: { points, "stroke-width": 3, class: "fill-stop-rest stroke-surface", ...HALO },
    },
    label("34", box, 10),
  ];
}

function diamond(box: number): SvgNode[] {
  const c = box / 2;
  const far = box - 1.5;
  return [
    {
      tag: "polygon",
      attrs: {
        points: `${c},1.5 ${far},${c} ${c},${far} 1.5,${c}`,
        "stroke-width": 3,
        class: "fill-stop-fuel stroke-surface",
        ...HALO,
      },
    },
    icon(Fuel, 13, box, ICON_STROKE),
  ];
}

const SPECS: Record<StopKind, () => GlyphSpec> = {
  start: () => ({
    size: 24,
    nodes: [
      ...ringCircle(24, "stroke-stop-load"),
      { tag: "circle", attrs: { cx: 12, cy: 12, r: 3, class: "fill-ink" } },
    ],
  }),
  pickup: () => ({ size: 26, nodes: square(26, "P") }),
  dropoff: () => ({ size: 26, nodes: square(26, "D") }),
  fuel: () => ({ size: 24, nodes: diamond(24) }),
  break: () => ({
    size: 22,
    nodes: [...ringCircle(22, "stroke-stop-rest"), icon(Pause, 12, 22, "stroke-stop-rest")],
  }),
  rest: () => ({
    size: 24,
    nodes: [
      {
        tag: "circle",
        attrs: {
          cx: 12,
          cy: 12,
          r: 10.5,
          "stroke-width": 3,
          class: "fill-stop-rest stroke-surface",
          ...HALO,
        },
      },
      icon(BedDouble, 13, 24, ICON_STROKE),
    ],
  }),
  restart: () => ({ size: 28, nodes: hexagon(28) }),
  // The end of the trip never has its own marker; the timeline draws the dropoff glyph for it.
  end: () => ({ size: 26, nodes: square(26, "D") }),
};

export function glyphSpec(kind: StopKind): GlyphSpec {
  return SPECS[kind]();
}

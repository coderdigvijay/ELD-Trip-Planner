import type { ReactElement } from "react";

import { HOUR_PATH, TICK_PATH, x } from "./geometry";
import {
  BAND_Y0,
  BAND_Y1,
  FRAME_W,
  GRID_X0,
  GRID_X1,
  GRID_Y1,
  HEAVY_W,
  HOUR_W,
  ROW_TOP,
  RULE_W,
  TICK_W,
  TOTAL_X0,
  TOTAL_X1,
} from "./layout";
import { FONT_SANS, INK, SURFACE } from "./tokens";

// The static printed form (LOG_SHEET_RENDER_SPEC 2.1 to 2.7, printed parts only). Module-level constant
// element: React never re-diffs it. Lines are non-scaling so hairlines stay crisp at any render size.

const NS = { vectorEffect: "non-scaling-stroke" } as const;

type Anchor = "start" | "middle" | "end";
interface PrintedText {
  x: number;
  y: number;
  t: string;
  size?: number;
  bold?: boolean;
  anchor?: Anchor;
  fill?: string;
}

/** [x1, x2, y, width] */
type HRule = readonly [number, number, number, number];

const H_RULES: readonly HRule[] = [
  // Date fields
  [330, 400, 40, RULE_W],
  [420, 492, 40, RULE_W],
  [512, 580, 40, RULE_W],
  // From / To
  [110, 480, 88, RULE_W],
  [540, 944, 88, RULE_W],
  // Driver, carrier, main office, home terminal
  [456, 944, 112, RULE_W],
  [456, 944, 152, RULE_W],
  [456, 944, 194, RULE_W],
  [456, 944, 236, RULE_W],
  // Row rules and total hours column
  [GRID_X0, GRID_X1, ROW_TOP.sleeper, FRAME_W],
  [GRID_X0, GRID_X1, ROW_TOP.driving, FRAME_W],
  [GRID_X0, GRID_X1, ROW_TOP.on_duty, FRAME_W],
  [TOTAL_X0, TOTAL_X1, ROW_TOP.sleeper, HOUR_W],
  [TOTAL_X0, TOTAL_X1, ROW_TOP.driving, HOUR_W],
  [TOTAL_X0, TOTAL_X1, ROW_TOP.on_duty, HOUR_W],
  [TOTAL_X0, TOTAL_X1, GRID_Y1, HOUR_W],
  [TOTAL_X0, TOTAL_X1, 504, HOUR_W],
  [TOTAL_X0, TOTAL_X1, 508, HOUR_W],
  // Remarks: heavy bottom rules
  [40, 364, 812, HEAVY_W],
  [628, 944, 812, HEAVY_W],
  // Shipping documents
  [44, 200, 676, RULE_W],
  [44, 200, 736, RULE_W],
  // Recap fill lines (values are written above them)
  [144, 208, 884, RULE_W],
  [300, 362, 884, RULE_W],
  [380, 442, 884, RULE_W],
  [460, 522, 884, RULE_W],
  [620, 682, 884, RULE_W],
  [700, 762, 884, RULE_W],
  [780, 842, 884, RULE_W],
  [40, 944, 988, HEAVY_W],
];

const BOXES: readonly (readonly [number, number, number, number])[] = [
  [108, 128, 164, 44],
  [280, 128, 154, 44],
  [108, 198, 326, 42],
];

const recapBody = (x0: number, lines: readonly string[]): PrintedText[] =>
  lines.map((t, i) => ({ x: x0, y: 898 + i * 14, t }));

const RECAP_FROM_ON_DUTY = ["On duty", "hours", "today,", "Total lines", "3 & 4"];
const RECAP_A = (n: number) => [
  "A. Total",
  "hours on",
  `duty last ${n}`,
  "days",
  "including",
  "today.",
];
const RECAP_B = (hr: number) => [
  "B. Total",
  "hours",
  "available",
  "tomorrow",
  `${hr} hr.`,
  "minus A*",
];
const RECAP_C = (n: number) => [
  "C. Total",
  "hours on",
  `duty last ${n}`,
  "days",
  "including",
  "today.",
];

const TEXTS: readonly PrintedText[] = [
  { x: 44, y: 38, t: "Drivers Daily Log", size: 28, bold: true },
  { x: 118, y: 58, t: "(24 hours)", size: 11, anchor: "middle" },
  { x: 365, y: 56, t: "(month)", anchor: "middle" },
  { x: 456, y: 56, t: "(day)", anchor: "middle" },
  { x: 546, y: 56, t: "(year)", anchor: "middle" },
  { x: 406, y: 40, t: "/", size: 22 },
  { x: 498, y: 40, t: "/", size: 22 },
  { x: 64, y: 84, t: "From:", size: 13, bold: true },
  { x: 510, y: 84, t: "To:", size: 13, bold: true },
  { x: 190, y: 188, t: "Total Miles Driving Today", bold: true, anchor: "middle" },
  { x: 357, y: 188, t: "Total Mileage Today", bold: true, anchor: "middle" },
  { x: 271, y: 256, t: "Truck/Tractor and Trailer Numbers or", anchor: "middle" },
  { x: 271, y: 270, t: "License Plate(s)/State (show each unit)", anchor: "middle" },
  { x: 700, y: 125, t: "Driver", bold: true, anchor: "middle" },
  { x: 700, y: 166, t: "Name of Carrier or Carriers", bold: true, anchor: "middle" },
  { x: 700, y: 208, t: "Main Office Address", bold: true, anchor: "middle" },
  { x: 700, y: 250, t: "Home Terminal Address", bold: true, anchor: "middle" },
  // Hour band
  { x: 126, y: 316, t: "Mid-", fill: SURFACE },
  { x: 126, y: 330, t: "night", fill: SURFACE },
  { x: 891, y: 316, t: "Mid-", fill: SURFACE, anchor: "end" },
  { x: 891, y: 330, t: "night", fill: SURFACE, anchor: "end" },
  { x: 930, y: 316, t: "Total", fill: SURFACE, anchor: "middle" },
  { x: 930, y: 330, t: "Hours", fill: SURFACE, anchor: "middle" },
  { x: x(720), y: 330, t: "Noon", size: 10.5, bold: true, fill: SURFACE, anchor: "middle" },
  ...Array.from({ length: 23 }, (_, i): PrintedText[] => {
    const h = i + 1;
    return h === 12
      ? []
      : [
          {
            x: x(h * 60),
            y: 330,
            t: String(h > 12 ? h - 12 : h),
            size: 10.5,
            bold: true,
            fill: SURFACE,
            anchor: "middle",
          },
        ];
  }).flat(),
  // Row labels
  { x: 44, y: 358, t: "1. Off Duty", size: 11, bold: true },
  { x: 44, y: 386, t: "2. Sleeper", size: 11, bold: true },
  { x: 44, y: 399, t: "Berth", size: 11, bold: true },
  { x: 44, y: 430, t: "3. Driving", size: 11, bold: true },
  { x: 44, y: 458, t: "4. On Duty", size: 11, bold: true },
  { x: 44, y: 471, t: "(not driving)", size: 11, bold: true },
  // Remarks and shipping
  { x: 44, y: 532, t: "Remarks", size: 14, bold: true },
  { x: 48, y: 632, t: "Shipping", size: 13, bold: true },
  { x: 48, y: 650, t: "Documents:", size: 13, bold: true },
  { x: 48, y: 690, t: "DVL or Manifest No." },
  { x: 48, y: 704, t: "or" },
  { x: 48, y: 750, t: "Shipper & Commodity" },
  {
    x: 500,
    y: 788,
    t: "Enter name of place you reported and where released from work and when and where each change of duty occurred.",
    bold: true,
    anchor: "middle",
  },
  { x: 496, y: 806, t: "Use time standard of home terminal.", bold: true, anchor: "middle" },
  // Recap
  { x: 44, y: 836, t: "Recap:", bold: true },
  { x: 44, y: 850, t: "Complete at", bold: true },
  { x: 44, y: 870, t: "end of day", bold: true },
  ...recapBody(144, RECAP_FROM_ON_DUTY).map((r) => ({ ...r, bold: true })),
  { x: 226, y: 836, t: "70 Hour/", bold: true },
  { x: 226, y: 850, t: "8 Day", bold: true },
  { x: 226, y: 870, t: "Drivers", bold: true },
  { x: 300, y: 864, t: "A.", size: 13 },
  ...recapBody(300, RECAP_A(7)),
  { x: 380, y: 864, t: "B.", size: 13 },
  ...recapBody(380, RECAP_B(70)),
  { x: 460, y: 864, t: "C.", size: 13 },
  ...recapBody(460, RECAP_C(8)),
  { x: 540, y: 850, t: "60 Hour/ 7", bold: true },
  { x: 540, y: 870, t: "Day Drivers", bold: true },
  { x: 620, y: 864, t: "A.", size: 13 },
  ...recapBody(620, RECAP_A(6)),
  { x: 700, y: 864, t: "B.", size: 13 },
  ...recapBody(700, RECAP_B(60)),
  { x: 780, y: 864, t: "C.", size: 13 },
  ...recapBody(780, RECAP_C(7)),
  ...["*If you took 34", "consecutive", "hours off duty", "you have 70", "hours available"].map(
    (t, i): PrintedText => ({ x: 856, y: 836 + i * 14, t }),
  ),
];

function renderText(t: PrintedText, index: number): ReactElement {
  return (
    <text
      key={index}
      x={t.x}
      y={t.y}
      fontSize={t.size ?? 10}
      fontWeight={t.bold ? 600 : 400}
      textAnchor={t.anchor ?? "start"}
      fill={t.fill ?? INK}
    >
      {t.t}
    </text>
  );
}

const hourLabels = TEXTS.filter((t) => t.fill === SURFACE);
const inkTexts = TEXTS.filter((t) => t.fill !== SURFACE);

export const BLANK_FORM: ReactElement = (
  <g data-part="blank-form" fontFamily={FONT_SANS}>
    <g stroke={INK} fill="none">
      {H_RULES.map(([x1, x2, yy, w]) => (
        <line key={`${x1}-${x2}-${yy}`} x1={x1} x2={x2} y1={yy} y2={yy} strokeWidth={w} {...NS} />
      ))}
      {BOXES.map(([bx, by, bw, bh]) => (
        <rect
          key={`${bx}-${by}`}
          x={bx}
          y={by}
          width={bw}
          height={bh}
          strokeWidth={FRAME_W}
          {...NS}
        />
      ))}
      <line x1={40} x2={40} y1={544} y2={812} strokeWidth={HEAVY_W} {...NS} />
    </g>
    {inkTexts.map((t, i) => renderText(t, i))}
    <text x={600} y={32} fontSize={10} fill={INK} xmlSpace="preserve">
      <tspan fontWeight={600}>Original</tspan>
      <tspan fontWeight={400}> - File at home terminal.</tspan>
    </text>
    <text x={600} y={50} fontSize={10} fill={INK} xmlSpace="preserve">
      <tspan fontWeight={600}>Duplicate</tspan>
      <tspan fontWeight={400}> - Driver retains in his/her possession for 8 days.</tspan>
    </text>
    <rect
      x={GRID_X0}
      y={BAND_Y0}
      width={TOTAL_X1 - GRID_X0}
      height={BAND_Y1 - BAND_Y0}
      fill={INK}
    />
    {hourLabels.map((t, i) => renderText(t, i))}
    <g data-part="grid" stroke={INK} fill="none" shapeRendering="crispEdges">
      <rect
        x={GRID_X0}
        y={BAND_Y1}
        width={GRID_X1 - GRID_X0}
        height={GRID_Y1 - BAND_Y1}
        strokeWidth={FRAME_W}
        {...NS}
      />
      <path d={HOUR_PATH} strokeWidth={HOUR_W} {...NS} />
      <path d={TICK_PATH} strokeWidth={TICK_W} {...NS} />
    </g>
  </g>
);

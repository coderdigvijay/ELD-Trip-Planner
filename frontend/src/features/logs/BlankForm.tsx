import type { ReactElement } from "react";

import { HOUR_PATH, TICK_PATH, x } from "./geometry";
import {
  BAND_LINE1_Y,
  BAND_LINE2_Y,
  BAND_TOTAL_X,
  BAND_Y0,
  BAND_Y1,
  COPY_NOTE_X,
  COPY_NOTE_Y,
  FORM_BOXES,
  FORM_H_RULES,
  FRAME_W,
  GRID_X0,
  GRID_X1,
  GRID_Y1,
  HEAVY_W,
  HOUR_W,
  MIDNIGHT_END_X,
  MIDNIGHT_START_X,
  REMARKS_LEFT_RULE,
  ROW_RULES,
  TICK_W,
  TOTAL_X1,
} from "./layout";
import { FONT_SANS, HOUR_SIZE, INK, SURFACE, TITLE_SIZE } from "./tokens";

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
  { x: 44, y: 38, t: "Drivers Daily Log", size: TITLE_SIZE, bold: true },
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
  { x: MIDNIGHT_START_X, y: BAND_LINE1_Y, t: "Mid-", fill: SURFACE },
  { x: MIDNIGHT_START_X, y: BAND_LINE2_Y, t: "night", fill: SURFACE },
  { x: MIDNIGHT_END_X, y: BAND_LINE1_Y, t: "Mid-", fill: SURFACE, anchor: "end" },
  { x: MIDNIGHT_END_X, y: BAND_LINE2_Y, t: "night", fill: SURFACE, anchor: "end" },
  { x: BAND_TOTAL_X, y: BAND_LINE1_Y, t: "Total", fill: SURFACE, anchor: "middle" },
  { x: BAND_TOTAL_X, y: BAND_LINE2_Y, t: "Hours", fill: SURFACE, anchor: "middle" },
  { x: x(720), y: 330, t: "Noon", size: HOUR_SIZE, bold: true, fill: SURFACE, anchor: "middle" },
  ...Array.from({ length: 23 }, (_, i): PrintedText[] => {
    const h = i + 1;
    return h === 12
      ? []
      : [
          {
            x: x(h * 60),
            y: 330,
            t: String(h > 12 ? h - 12 : h),
            size: HOUR_SIZE,
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
      {FORM_H_RULES.map(([x1, x2, yy, w]) => (
        <line key={`${x1}-${x2}-${yy}`} x1={x1} x2={x2} y1={yy} y2={yy} strokeWidth={w} {...NS} />
      ))}
      {FORM_BOXES.map(([bx, by, bw, bh]) => (
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
      <line
        x1={REMARKS_LEFT_RULE[0]}
        x2={REMARKS_LEFT_RULE[0]}
        y1={REMARKS_LEFT_RULE[1]}
        y2={REMARKS_LEFT_RULE[2]}
        strokeWidth={HEAVY_W}
        {...NS}
      />
    </g>
    {inkTexts.map((t, i) => renderText(t, i))}
    <text x={COPY_NOTE_X} y={COPY_NOTE_Y[0]} fontSize={10} fill={INK} xmlSpace="preserve">
      <tspan fontWeight={600}>Original</tspan>
      <tspan fontWeight={400}> - File at home terminal.</tspan>
    </text>
    <text x={COPY_NOTE_X} y={COPY_NOTE_Y[1]} fontSize={10} fill={INK} xmlSpace="preserve">
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
      {ROW_RULES.map(([x1, x2, yy, w]) => (
        <line key={yy} x1={x1} x2={x2} y1={yy} y2={yy} strokeWidth={w} {...NS} />
      ))}
      <path d={HOUR_PATH} strokeWidth={HOUR_W} {...NS} />
      <path d={TICK_PATH} strokeWidth={TICK_W} {...NS} />
    </g>
  </g>
);

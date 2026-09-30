import { ENTRY_LG, ENTRY_MD, FRAME_W, HALF_W, HEAVY_W, HOUR_W, RULE_W } from "./tokens";
import type { DutyStatus } from "./types";

// Single source of geometry for the log sheet (LOG_SHEET_RENDER_SPEC sections 1 to 3). ViewBox units.
export const VIEW_W = 1000;
export const VIEW_H = 1020;

export const GRID_X0 = 124;
export const GRID_W = 768;
export const GRID_X1 = GRID_X0 + GRID_W;
export const BAND_Y0 = 300;
export const BAND_Y1 = 336;
export const ROW_H = 36;
export const ROW_TOP: Record<DutyStatus, number> = {
  off: 336,
  sleeper: 372,
  driving: 408,
  on_duty: 444,
};
export const GRID_Y1 = 480;
export const TOTAL_X0 = 904;
export const TOTAL_X1 = 956;

export const STATUS_ORDER: readonly DutyStatus[] = ["off", "sleeper", "driving", "on_duty"];
export const STATUS_TERM: Record<DutyStatus, string> = {
  off: "Off duty",
  sleeper: "Sleeper berth",
  driving: "Driving",
  on_duty: "On duty (not driving)",
};

export const HALF_LEN = 18;
export const QUARTER_LEN = 11;

// Stroke weights live in tokens.ts (asserted equal to --log-* in index.css); re-exported here.
export { BRACKET_ARM, BRACKET_W, FRAME_W, HEAVY_W, HOUR_W, RULE_W, STATUS_W } from "./tokens";
export const TICK_W = HALF_W;

// Remarks drop zone.
export const BRACKET_Y0 = 482;
export const BRACKET_Y1 = 488;
export const DROP_Y0_GRID = GRID_Y1;
export const DROP_Y0_BRACKET = 488;
export const LEADER_Y0 = 504;
export const LEADER_Y1 = 524;
export const LABEL_Y = 530;
export const AX_LO = GRID_X0;
export const AX_HI = 895;
export const LABEL_RIGHT = 954;
export const SIN45 = Math.SQRT1_2;
export const MONO_ADVANCE = 0.6;

// ---- Printed form (LOG_SHEET_RENDER_SPEC 2.1 to 2.7) ----

/** [x1, x2, y, stroke width] */
export type HRule = readonly [number, number, number, number];
/** [x, y, width, height] */
export type Box = readonly [number, number, number, number];

export const FORM_LEFT = 40;
export const FORM_RIGHT = 944;
export const HEADER_LINE_X0 = 456;

/** Rules of the printed form outside the grid, in paint order. */
export const FORM_H_RULES: readonly HRule[] = [
  // Date fields
  [330, 400, 40, RULE_W],
  [420, 492, 40, RULE_W],
  [512, 580, 40, RULE_W],
  // From / To
  [110, 480, 88, RULE_W],
  [540, FORM_RIGHT, 88, RULE_W],
  // Driver, carrier, main office, home terminal
  [HEADER_LINE_X0, FORM_RIGHT, 112, RULE_W],
  [HEADER_LINE_X0, FORM_RIGHT, 152, RULE_W],
  [HEADER_LINE_X0, FORM_RIGHT, 194, RULE_W],
  [HEADER_LINE_X0, FORM_RIGHT, 236, RULE_W],
  // Total hours column
  [TOTAL_X0, TOTAL_X1, ROW_TOP.sleeper, HOUR_W],
  [TOTAL_X0, TOTAL_X1, ROW_TOP.driving, HOUR_W],
  [TOTAL_X0, TOTAL_X1, ROW_TOP.on_duty, HOUR_W],
  [TOTAL_X0, TOTAL_X1, GRID_Y1, HOUR_W],
  [TOTAL_X0, TOTAL_X1, 504, HOUR_W],
  [TOTAL_X0, TOTAL_X1, 508, HOUR_W],
  // Remarks: heavy bottom rules
  [FORM_LEFT, 364, 812, HEAVY_W],
  [628, FORM_RIGHT, 812, HEAVY_W],
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
  [FORM_LEFT, FORM_RIGHT, 988, HEAVY_W],
];

/** Row separators inside the grid (crispEdges group). */
export const ROW_RULES: readonly HRule[] = [ROW_TOP.sleeper, ROW_TOP.driving, ROW_TOP.on_duty].map(
  (yy): HRule => [GRID_X0, GRID_X1, yy, FRAME_W],
);

export const FORM_BOXES: readonly Box[] = [
  [108, 128, 164, 44],
  [280, 128, 154, 44],
  [108, 198, 326, 42],
];
/** Heavy left rule of the remarks block: [x, y1, y2]. */
export const REMARKS_LEFT_RULE = [FORM_LEFT, 544, 812] as const;
/** Original / Duplicate notes: [x, y]. */
export const COPY_NOTE_X = 600;
export const COPY_NOTE_Y = [32, 50] as const;

// Hour band captions (2.2). Start text is anchored start, end text anchored end.
export const MIDNIGHT_START_X = 127;
export const MIDNIGHT_END_X = 889;
export const BAND_LINE1_Y = 316;
export const BAND_LINE2_Y = 330;
export const BAND_TOTAL_X = 930;

// ---- Entries in pen (2.3 to 2.7) ----
export { ENTRY_LG, ENTRY_MD };
export const NOTE_SIZE = 10;

export const DATE_X = { mm: 365, dd: 456, yyyy: 546 } as const;
export const DATE_Y = 35;
export const FROM_POS = { x: 116, y: 83 } as const;
export const TO_POS = { x: 546, y: 83 } as const;
export const MILES_X = { driving: 190, total: 357 } as const;
export const MILES_Y = 158;
export const VEHICLE_POS = { x: 271, y: 225 } as const;
export const HEADER_LINE_X = 700;
export const HEADER_LINE_Y = {
  driver: 107,
  carrier: 147,
  mainOffice: 189,
  homeTerminal: 231,
} as const;
export const SHIPPING_DOC_POS = { x: 48, y: 670 } as const;
export const SHIPPER_X = 48;
export const SHIPPER_LAST_Y = 730;
export const SHIPPER_LINE_H = 12;

export const TOTALS_X = 954;
export const TOTALS_BASELINE_DY = 29;
export const GRAND_TOTAL_Y = 499;

export const RECAP_Y = 879;
export const RECAP_X = {
  today: 176,
  a: 331,
  b: 411,
  c: 491,
  a60: 651,
  b60: 731,
  c60: 811,
} as const;
export const RESTART_POS = { x: 856, y: 910, lineH: 13 } as const;

export const REMARK_TEXT_DX = 4;
export const REMARK_NOTE_DY = 13;

export const FOOTER_Y = 1008;
export const FOOTER_DATE_X = 44;
export const FOOTER_SHEET_X = 944;
/** Home terminal time base (2.7): footer row, text-anchor middle, same baseline as date and sheet. */
export const TIME_BASE_POS = { x: 500, y: FOOTER_Y } as const;

export interface TextBox {
  name: string;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

const FOOTNOTE_X = 856;
const FOOTNOTE_Y = [836, 850, 864, 878, 892] as const;
const FOOTNOTE_CHARS = 15;
const RESTART_MAX_LINES = 3;
const RESTART_CHARS = 14;
const RECAP_VALUE_CHARS = 5;
const TIME_BASE_CHARS = 38;
const SHEET_LABEL_CHARS = 13;
const DATE_CHARS = 10;
const TEXT_SIZE = 10;
/** Upper bound of an advance at size 10: mono is exactly 0.6 em, the sans faces stay under it. */
const ADVANCE = 0.6 * TEXT_SIZE;

function box(
  name: string,
  anchor: "start" | "middle" | "end",
  x: number,
  y: number,
  chars: number,
) {
  const w = chars * ADVANCE;
  const x0 = anchor === "start" ? x : anchor === "middle" ? x - w / 2 : x - w;
  return { name, x0, x1: x0 + w, y0: y - 0.8 * TEXT_SIZE, y1: y + 0.2 * TEXT_SIZE };
}

/**
 * Conservative bounding boxes of every text node in the recap and footer band (the 34 hr
 * footnote, recap values, restart note, footer date, time base and sheet label). Used by the
 * overlap test; the widths are upper bounds (0.6 em per character).
 */
export function bandTextBoxes(): TextBox[] {
  return [
    ...FOOTNOTE_Y.map((y, i) =>
      box(`footnote-${String(i)}`, "start", FOOTNOTE_X, y, FOOTNOTE_CHARS),
    ),
    ...Object.entries(RECAP_X).map(([k, x]) =>
      box(`recap-${k}`, "middle", x, RECAP_Y, RECAP_VALUE_CHARS),
    ),
    ...Array.from({ length: RESTART_MAX_LINES }, (_, i) =>
      box(
        `restart-${String(i)}`,
        "start",
        RESTART_POS.x,
        RESTART_POS.y + i * RESTART_POS.lineH,
        RESTART_CHARS,
      ),
    ),
    box("footer-date", "start", FOOTER_DATE_X, FOOTER_Y, DATE_CHARS),
    box("footer-time-base", "middle", TIME_BASE_POS.x, TIME_BASE_POS.y, TIME_BASE_CHARS),
    box("footer-sheet", "end", FOOTER_SHEET_X, FOOTER_Y, SHEET_LABEL_CHARS),
  ];
}

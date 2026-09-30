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

// Stroke weights (CSS px for the non-scaling form group, viewBox units for pen marks).
export const FRAME_W = 1.5;
export const HOUR_W = 1;
export const TICK_W = 0.75;
export const RULE_W = 0.75;
export const HEAVY_W = 2.5;
export const STATUS_W = 2.5;
export const BRACKET_W = 1;
export const BRACKET_ARM = 6;

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

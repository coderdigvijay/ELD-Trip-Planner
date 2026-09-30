import {
  BRACKET_Y0,
  BRACKET_Y1,
  GRID_W,
  GRID_X0,
  HALF_LEN,
  QUARTER_LEN,
  ROW_H,
  ROW_TOP,
  STATUS_ORDER,
} from "./layout";
import type { DutyStatus, LogSegment } from "./types";

/** Minute since midnight to viewBox x. Integer for every multiple of 15. */
export const x = (minute: number): number => GRID_X0 + (minute * GRID_W) / 1440;

/** Duty status to the y of its row centerline. */
export const y = (status: DutyStatus): number => ROW_TOP[status] + ROW_H / 2;

export interface SegmentIssue {
  index: number;
  kind: "gap" | "overlap" | "start" | "end" | "empty";
}

/** Structural check, no fixing: sorted, contiguous, 0..1440. */
export function segmentIssues(segments: readonly LogSegment[]): SegmentIssue[] {
  if (segments.length === 0) return [{ index: 0, kind: "empty" }];
  const issues: SegmentIssue[] = [];
  segments.forEach((seg, i) => {
    const prevEnd = i === 0 ? 0 : (segments[i - 1]?.end_min ?? 0);
    if (i === 0 && seg.start_min !== 0) issues.push({ index: i, kind: "start" });
    if (i > 0 && seg.start_min > prevEnd) issues.push({ index: i, kind: "gap" });
    if (i > 0 && seg.start_min < prevEnd) issues.push({ index: i, kind: "overlap" });
    if (seg.end_min <= seg.start_min) issues.push({ index: i, kind: "overlap" });
  });
  if ((segments[segments.length - 1]?.end_min ?? 0) !== 1440)
    issues.push({ index: segments.length - 1, kind: "end" });
  return issues;
}

/**
 * The duty line: horizontal run per segment on its row centerline, vertical connector at every status change.
 * On a gap or overlap a new subpath starts (never a false connector).
 */
export function dutyPath(segments: readonly LogSegment[]): string {
  const parts: string[] = [];
  let prev: LogSegment | undefined;
  for (const seg of segments) {
    if (!prev || seg.start_min !== prev.end_min) {
      parts.push(`M${x(seg.start_min)} ${y(seg.status)} H${x(seg.end_min)}`);
    } else {
      if (seg.status !== prev.status) parts.push(`V${y(seg.status)}`);
      parts.push(`H${x(seg.end_min)}`);
    }
    prev = seg;
  }
  return parts.join(" ");
}

export interface BracketSpan {
  startMin: number;
  endMin: number;
  x0: number;
  x1: number;
}

/** One span per segment the API flags stationary. */
export function brackets(segments: readonly LogSegment[]): BracketSpan[] {
  return segments
    .filter((s) => s.stationary)
    .map((s) => ({
      startMin: s.start_min,
      endMin: s.end_min,
      x0: x(s.start_min),
      x1: x(s.end_min),
    }));
}

/** All brackets as one path: U, 6 unit arms, 6 unit deep. */
export function bracketPath(spans: readonly BracketSpan[]): string {
  return spans
    .map((b) => `M${b.x0} ${BRACKET_Y0} V${BRACKET_Y1} H${b.x1} V${BRACKET_Y0}`)
    .join(" ");
}

/** Full-height hour lines x(60) .. x(1380), one path, computed once at import. */
export const HOUR_PATH: string = Array.from({ length: 23 }, (_, i) => {
  const px = x((i + 1) * 60);
  return `M${px} ${ROW_TOP.off} V${ROW_TOP.on_duty + ROW_H}`;
}).join(" ");

function tickSpan(status: DutyStatus, len: number): [number, number] {
  const top = ROW_TOP[status];
  // Rows 1 and 2: ticks hang from the top edge. Rows 3 and 4: ticks rise from the bottom edge.
  return status === "off" || status === "sleeper"
    ? [top, top + len]
    : [top + ROW_H - len, top + ROW_H];
}

/** Half-hour (18) and quarter-hour (11) ticks for the four rows, one path, computed once at import. */
export const TICK_PATH: string = STATUS_ORDER.flatMap((status) => {
  const out: string[] = [];
  for (let step = 0; step < 96; step += 1) {
    if (step % 4 === 0) continue; // hour lines are HOUR_PATH
    const [a, b] = tickSpan(status, step % 2 === 0 ? HALF_LEN : QUARTER_LEN);
    out.push(`M${x(step * 15)} ${a} V${b}`);
  }
  return out;
}).join(" ");

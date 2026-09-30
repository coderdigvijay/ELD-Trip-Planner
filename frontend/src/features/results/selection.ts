import type { HoverStore } from "./hoverStore";
import { isoParts, dayKey } from "./time";
import type { LogDayRef, Stop, TripTimezone } from "./types";

/**
 * List, map and log sync contract (DESIGN_SYSTEM 6.5). The App owns one `selectedStopId`
 * and passes these three props to MapView and StopTimeline.
 */
export interface SelectionProps {
  /** The selected stop id ("s3"), or null. Highlights the row and the marker. */
  selectedStopId: string | null;
  /** Row or marker chosen (id), or Escape pressed (null). */
  onSelectStop: (stopId: string | null) => void;
  /** Sheet (1-based `sheet_index`) of the chosen stop, so the App can switch the log tab. */
  onSelectDay?: (sheetIndex: number) => void;
  /** Hover bonus, never required. Shared by the rows and the markers (hoverStore.ts). */
  hover?: HoverStore;
}

/** The moment a stop starts on its log sheet: pass to `DailyLogs` as `focus`. */
export interface StopLogFocus {
  sheetIndex: number;
  minute: number;
}

/**
 * Sheet and minute-from-midnight of a stop's arrival, read from the ISO string in the trip's
 * frozen offset. Not HOS math: it only locates the stop on the sheet the API already produced.
 */
export function logFocusForStop(
  stop: Stop,
  days: readonly LogDayRef[],
  timezone: TripTimezone,
): StopLogFocus | undefined {
  const parts = isoParts(stop.arrive_at, timezone);
  const day = days.find((d) => d.date === dayKey(parts.date));
  if (!day) return undefined;
  return { sheetIndex: day.sheet_index, minute: parts.minuteOfDay };
}

/** 1-based sheet index for a calendar day key, or undefined when the day has no sheet. */
export function sheetIndexForDate(days: readonly LogDayRef[], date: string): number | undefined {
  return days.find((d) => d.date === date)?.sheet_index;
}

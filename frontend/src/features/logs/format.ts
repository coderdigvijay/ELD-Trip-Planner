import { MONO_ADVANCE } from "./layout";

/** 10, 1.75, 4.5, 0, 24. Never "10.00". */
export function formatHours(hours: number): string {
  const rounded = Math.round(hours * 100) / 100;
  return String(Object.is(rounded, -0) ? 0 : rounded);
}

/** 350, 337.7, 0. No thousands separator. */
export function formatMiles(miles: number): string {
  const rounded = Math.round(miles * 10) / 10;
  return String(Object.is(rounded, -0) ? 0 : rounded);
}

/** "H:MM" for the day summary line (display only). */
export function formatHM(hours: number): string {
  const totalMin = Math.round(hours * 60);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return `${h}:${String(m).padStart(2, "0")}`;
}

/** "HH:MM" from minutes since the sheet's midnight (1440 shows as 24:00). */
export function formatClock(minute: number): string {
  const h = Math.floor(minute / 60);
  const m = minute % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export interface DateParts {
  mm: string;
  dd: string;
  yyyy: string;
}

/** String split on purpose: new Date("YYYY-MM-DD") parses as UTC midnight and shifts the day west of UTC. */
export function splitDate(date: string): DateParts {
  const [yyyy = "", mm = "", dd = ""] = date.split("-");
  return { mm, dd, yyyy };
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

/** UTC in, UTC out: the weekday of a calendar date never depends on the viewer's time zone. */
export function weekdayOf(date: string): string {
  const { yyyy, mm, dd } = splitDate(date);
  return WEEKDAYS[new Date(Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd))).getUTCDay()] ?? "";
}

/** "Fri Apr 9, 2021" */
export function formatLongDate(date: string): string {
  const { yyyy, mm, dd } = splitDate(date);
  const month = MONTHS[Number(mm) - 1] ?? "";
  return `${weekdayOf(date)} ${month} ${Number(dd)}, ${yyyy}`;
}

export interface FittedText {
  /** Text to draw (may end in "..."). */
  text: string;
  size: number;
  /** True when shrunk or truncated: the full text belongs in a <title>. */
  clipped: boolean;
}

/**
 * Fit monospace text into maxWidth with arithmetic only (advance is exactly 0.6 em):
 * as is, else shrink to minSize, else truncate at minSize with "...".
 */
export function fitMono(
  text: string,
  maxWidth: number,
  size: number,
  minSize = size * 0.8,
): FittedText {
  const n = text.length;
  if (n === 0 || MONO_ADVANCE * size * n <= maxWidth) return { text, size, clipped: false };
  const shrunk = Math.max(minSize, maxWidth / (MONO_ADVANCE * n));
  if (MONO_ADVANCE * shrunk * n <= maxWidth + 1e-9) return { text, size: shrunk, clipped: true };
  return {
    text: truncate(text, Math.floor(maxWidth / (MONO_ADVANCE * minSize))),
    size: minSize,
    clipped: true,
  };
}

/** First k - 3 chars plus three ASCII dots; strings that already fit are returned as is. */
export function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(0, maxChars - 3))}...`;
}

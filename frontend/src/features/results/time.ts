import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";

import type { TripTimezone } from "./types";

/**
 * Every clock in the results is the trip's frozen offset ("-04:00"), never the browser zone, so
 * the shown time equals the local part of the API's ISO string (DESIGN_SYSTEM 4.4).
 */
export function inTripZone(iso: string, timezone: TripTimezone): TZDate {
  return new TZDate(iso, timezone.utc_offset);
}

export function dayKey(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function isoParts(iso: string, timezone: TripTimezone) {
  const date = inTripZone(iso, timezone);
  return {
    date,
    minuteOfDay: date.getHours() * 60 + date.getMinutes(),
  };
}

/** "08:00", 24 hour. */
export function formatClock(iso: string, timezone: TripTimezone): string {
  return format(inTripZone(iso, timezone), "HH:mm");
}

/** "Tue, Sep 29". */
export function formatDayLabel(date: Date): string {
  return format(date, "EEE, MMM d");
}

/** "All times EDT (UTC-04:00), home terminal time". */
export function zoneLabel(timezone: TripTimezone): string {
  return `All times ${timezone.abbreviation} (UTC${timezone.utc_offset}), home terminal time`;
}

/** "7 h 45 m", "30 m", "4 h". Rounds to whole minutes. */
export function formatDuration(hours: number): string {
  const total = Math.max(0, Math.round(hours * 60));
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} m`;
  return m === 0 ? `${h} h` : `${h} h ${m} m`;
}

/** "2 d 7 h 30 m" for a trip span of a day or more, otherwise like formatDuration. */
export function formatSpan(hours: number): string {
  const total = Math.max(0, Math.round(hours * 60));
  const d = Math.floor(total / 1440);
  if (d === 0) return formatDuration(hours);
  const rest = total % 1440;
  const h = Math.floor(rest / 60);
  const m = rest % 60;
  return [`${d} d`, h > 0 ? `${h} h` : "", m > 0 ? `${m} m` : ""].filter(Boolean).join(" ");
}

const MILES = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/** "1,204 mi", whole miles. */
export function formatMilesWhole(miles: number): string {
  return `${MILES.format(Math.round(miles))} mi`;
}

/** 58.5, 12, 3.25: up to two decimals, no trailing zeros. */
export function formatHoursPlain(hours: number): string {
  return String(Math.round(hours * 100) / 100);
}

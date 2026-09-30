import type { TZDate } from "@date-fns/tz";
import { addDays, startOfDay } from "date-fns";

import { sheetIndexForDate } from "./selection";
import { dayKey, formatClock, formatDayLabel, inTripZone } from "./time";
import type { LogDayRef, Stop, TimelineEvent, TripTimezone } from "./types";

export interface DriveLeg {
  hours: number;
  miles: number;
}

export interface TimelineRow {
  key: string;
  stop: Stop;
  /** True for the "(cont.)" row of a stop that runs past midnight. */
  cont: boolean;
  time: string;
  /** Hours shown on this row. A cont row shows only the part after midnight. */
  durationH: number;
  /** Driving that ended at this stop (a thin connector row above it). */
  drive?: DriveLeg;
}

export interface DayGroup {
  key: string;
  label: string;
  dayNumber: number;
  sheetIndex?: number;
  rows: TimelineRow[];
}

const MS_PER_HOUR = 3_600_000;

function driveLegs(timeline: readonly TimelineEvent[]): Map<number, DriveLeg> {
  const legs = new Map<number, DriveLeg>();
  for (const event of timeline) {
    if (event.status !== "driving") continue;
    legs.set(Date.parse(event.end_at), {
      hours: (event.end_min - event.start_min) / 60,
      miles: event.end_mi - event.start_mi,
    });
  }
  return legs;
}

/**
 * Groups stops by the local date of `arrive_at`, and repeats a stop that outlasts midnight under
 * each later date marked "(cont.)" (DESIGN_SYSTEM 4.4, RESEARCH A3). Display grouping only.
 */
export function buildDayGroups(
  stops: readonly Stop[],
  timeline: readonly TimelineEvent[],
  timezone: TripTimezone,
  days: readonly LogDayRef[],
): DayGroup[] {
  const legs = driveLegs(timeline);
  const groups = new Map<string, DayGroup>();

  const groupFor = (at: TZDate): DayGroup => {
    const key = dayKey(at);
    let group = groups.get(key);
    if (!group) {
      const sheetIndex = sheetIndexForDate(days, key);
      group = {
        key,
        label: formatDayLabel(at),
        dayNumber: sheetIndex ?? groups.size + 1,
        sheetIndex,
        rows: [],
      };
      groups.set(key, group);
    }
    return group;
  };

  for (const stop of stops) {
    groupFor(inTripZone(stop.arrive_at, timezone)).rows.push({
      key: stop.id,
      stop,
      cont: false,
      time: formatClock(stop.arrive_at, timezone),
      durationH: stop.duration_h,
      drive: legs.get(Date.parse(stop.arrive_at)),
    });

    const depart = inTripZone(stop.depart_at, timezone);
    let cursor = addDays<TZDate, TZDate>(
      startOfDay<TZDate, TZDate>(inTripZone(stop.arrive_at, timezone)),
      1,
    );
    while (cursor.getTime() < depart.getTime()) {
      const remainingH = Math.min(24, (depart.getTime() - cursor.getTime()) / MS_PER_HOUR);
      groupFor(cursor).rows.push({
        key: `${stop.id}-cont-${dayKey(cursor)}`,
        stop,
        cont: true,
        time: "00:00",
        durationH: remainingH,
      });
      cursor = addDays<TZDate, TZDate>(cursor, 1);
    }
  }
  return [...groups.values()];
}

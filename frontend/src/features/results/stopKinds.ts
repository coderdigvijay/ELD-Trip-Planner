import type { DutyStatus, Stop, StopKind } from "./types";

/** Terms follow the FMCSA guide (DESIGN_SYSTEM 8). */
export const KIND_LABEL: Record<StopKind, string> = {
  start: "Start",
  pickup: "Pickup",
  dropoff: "Dropoff",
  fuel: "Fuel",
  break: "30-min break",
  rest: "10-hr rest",
  restart: "34-hr restart",
  end: "Released from duty",
};

/** Marker merge priority, highest first (DESIGN_SYSTEM 6.3). */
export const KIND_PRIORITY: readonly StopKind[] = [
  "dropoff",
  "pickup",
  "restart",
  "rest",
  "fuel",
  "break",
  "start",
  "end",
];

export const STATUS_CODE: Record<DutyStatus, string> = {
  off: "OFF",
  sleeper: "SB",
  driving: "D",
  on_duty: "ON",
};

export const STATUS_NAME: Record<DutyStatus, string> = {
  off: "Off duty",
  sleeper: "Sleeper berth",
  driving: "Driving",
  on_duty: "On duty (not driving)",
};

/** Legend and merge order for stop kinds that own a marker. `end` never has its own. */
export const LEGEND_KINDS: readonly StopKind[] = [
  "start",
  "pickup",
  "dropoff",
  "fuel",
  "break",
  "rest",
  "restart",
];

/** "Fuel, near Hagerstown, MD" style name used for titles and accessible names. */
export function stopName(stop: Pick<Stop, "kind" | "label">): string {
  return `${KIND_LABEL[stop.kind]}, ${stop.label}`;
}

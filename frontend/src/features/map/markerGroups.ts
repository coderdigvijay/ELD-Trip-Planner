import { KIND_PRIORITY } from "../results/stopKinds";
import type { Stop } from "../results/types";

export interface MarkerGroup {
  /** Id of the highest-priority stop; this is what a marker click selects. */
  id: string;
  primary: Stop;
  /** Every stop at this coordinate, in arrival order (the tooltip and title list all of them). */
  stops: Stop[];
}

const priority = (stop: Stop): number => KIND_PRIORITY.indexOf(stop.kind);

/**
 * Stops at the same coordinate share one marker (DESIGN_SYSTEM 6.3), so `end` always lands on the
 * dropoff marker. Nothing is hidden: the count only grows a "+N" badge.
 */
export function groupStops(stops: readonly Stop[]): MarkerGroup[] {
  const byPlace = new Map<string, Stop[]>();
  for (const stop of stops) {
    const key = `${stop.lat.toFixed(5)},${stop.lng.toFixed(5)}`;
    const list = byPlace.get(key);
    if (list) list.push(stop);
    else byPlace.set(key, [stop]);
  }
  return [...byPlace.values()].map((list) => {
    const primary = [...list].sort((a, b) => priority(a) - priority(b))[0] ?? list[0];
    if (!primary) throw new Error("empty marker group");
    return { id: primary.id, primary, stops: list };
  });
}

/** Marker group holding a stop id (the end row of a merged dropoff selects the dropoff marker). */
export function groupIdOf(groups: readonly MarkerGroup[], stopId: string | null): string | null {
  if (!stopId) return null;
  return groups.find((g) => g.stops.some((s) => s.id === stopId))?.id ?? null;
}

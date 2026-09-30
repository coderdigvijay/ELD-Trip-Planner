import type { TripWarning } from "./types";

export interface WarningCopy {
  title: string;
  body: string;
}

// Plain words for the codes API_CONTRACT 5.2 lists. The code is an open enum, so an unknown
// code falls back to the API's own message and is never dropped.
const COPY: Record<string, WarningCopy> = {
  CAR_PROFILE_USED: {
    title: "Car route used",
    body: "No truck route was found, so the distance and drive time come from a car route. A truck may need more time or a different road.",
  },
  LABELS_APPROXIMATED: {
    title: "Some place names are approximate",
    body: 'Stops and log remarks may read "near City, ST" or show coordinates, because place lookups were limited or unavailable.',
  },
  CYCLE_RESTART_AT_START: {
    title: "The trip starts with a 34-hour restart",
    body: "Your cycle hours were 69.5 or more, so the plan opens with a restart from 00:00 and the start time you chose is not used.",
  },
};

export function warningCopy(warning: TripWarning): WarningCopy {
  return (
    COPY[warning.code] ?? {
      title: "Note about this plan",
      body: warning.message,
    }
  );
}

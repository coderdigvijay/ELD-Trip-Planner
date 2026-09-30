import { ApiError, NetworkError } from "@/services/errors";

import { isTripFieldName, type LocationFieldName, type TripFieldName } from "./schema";

/**
 * Maps a failed plan to UI recovery (DESIGN_SYSTEM 4.5, ARCHITECTURE section 6).
 * Branches on `error.code` only, never on `message`.
 */

export interface FieldProblem {
  field: TripFieldName;
  message: string;
}

export type RecoveryAction =
  | { type: "edit"; field: TripFieldName; label: string }
  | { type: "retry"; countdownS: number | null }
  | { type: "none" };

export interface AlertFailure {
  kind: "alert";
  tone: "danger" | "warn";
  title: string;
  body: string;
  /** Rendered in mono after the body when present. */
  requestId?: string;
  /** Countdown text replaces the body when set. */
  action: RecoveryAction;
}

export interface FieldFailure {
  kind: "fields";
  problems: FieldProblem[];
}

export type PlanFailure = AlertFailure | FieldFailure;

const FALLBACK_RETRY_S = 60;
const MAX_QUOTA_COUNTDOWN_S = 300;

const LOCATION_LABELS: Record<LocationFieldName, string> = {
  current_location: "Edit current location",
  pickup_location: "Edit pickup",
  dropoff_location: "Edit dropoff",
};

/** `pickup_location.lat` maps to its root field; `log_header.x` keeps its full path. */
export function toFormField(path: string | undefined): TripFieldName | null {
  if (!path) return null;
  const [root = ""] = path.split(".");
  if (root === "current_location" || root === "pickup_location" || root === "dropoff_location") {
    return root;
  }
  return isTripFieldName(path) ? path : null;
}

function fieldProblems(error: ApiError): FieldProblem[] {
  if (error.code === "VALIDATION_ERROR" && error.details.length > 0) {
    const problems: FieldProblem[] = [];
    for (const detail of error.details) {
      const field = toFormField(detail.field);
      if (field) problems.push({ field, message: detail.message });
    }
    return problems;
  }
  const field = toFormField(error.field);
  return field ? [{ field, message: error.message }] : [];
}

function retryAlert(
  tone: "danger" | "warn",
  title: string,
  body: string,
  countdownS: number | null,
): AlertFailure {
  return { kind: "alert", tone, title, body, action: { type: "retry", countdownS } };
}

function unexpected(requestId: string | undefined): AlertFailure {
  return {
    kind: "alert",
    tone: "danger",
    title: "The planner hit an unexpected error",
    body: requestId
      ? "Try again. If it keeps happening, quote reference"
      : "Try again. If it keeps happening, reload the page.",
    requestId,
    action: { type: "retry", countdownS: null },
  };
}

export function describePlanError(error: unknown): PlanFailure {
  if (error instanceof NetworkError) {
    return retryAlert(
      "danger",
      "Could not reach the server",
      "Check your connection and try again.",
      null,
    );
  }
  if (!(error instanceof ApiError)) return unexpected(undefined);

  switch (error.code) {
    case "VALIDATION_ERROR":
    case "LOCATION_NOT_FOUND":
    case "UNSUPPORTED_LOCATION":
    case "AMBIGUOUS_LOCATION": {
      const problems = fieldProblems(error);
      if (problems.length > 0) return { kind: "fields", problems };
      // The request itself was rejected but no field is named (body size, JSON): no field to point at.
      return retryAlert("danger", "The trip could not be sent", error.message, null);
    }
    case "ROUTE_NOT_FOUND": {
      const field = toFormField(error.field);
      const locationField =
        field === "current_location" || field === "pickup_location" || field === "dropoff_location"
          ? field
          : null;
      return {
        kind: "alert",
        tone: "danger",
        title: "No drivable route found",
        body: error.message,
        action: locationField
          ? { type: "edit", field: locationField, label: LOCATION_LABELS[locationField] }
          : { type: "edit", field: "current_location", label: "Edit locations" },
      };
    }
    case "TRIP_TOO_LONG":
      return {
        kind: "alert",
        tone: "danger",
        title: "This trip is too long to plan",
        body: error.message,
        action: { type: "edit", field: "current_location", label: "Edit locations" },
      };
    case "RATE_LIMITED":
      return retryAlert(
        "warn",
        "Too many requests right now",
        "",
        error.retryAfterS ?? FALLBACK_RETRY_S,
      );
    case "UPSTREAM_QUOTA_EXCEEDED": {
      const wait = error.retryAfterS;
      if (wait !== undefined && wait <= MAX_QUOTA_COUNTDOWN_S) {
        return retryAlert("warn", "Routing limit reached", error.message, wait);
      }
      return {
        kind: "alert",
        tone: "warn",
        title: "Routing limit reached",
        body: error.message,
        action: { type: "none" },
      };
    }
    case "UPSTREAM_UNAVAILABLE":
      return retryAlert(
        "danger",
        "The routing service is not responding",
        "This is on the routing provider's side, not your trip. Try again in a minute.",
        null,
      );
    default:
      return unexpected(error.requestId);
  }
}

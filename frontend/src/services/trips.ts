import { apiClient } from "./client";
import { unwrap } from "./errors";
import type { components } from "./api-types";

type Schemas = components["schemas"];

export type PlanTripRequest = Schemas["PlanTripRequest"];
export type PlanTripResponse = Schemas["PlanTripResponse"];
export type PlaceInput = Schemas["PlaceInput"];
export type LocationInput = Schemas["LocationInput"];

/** Deadline for the POST itself, measured from when it is sent (DESIGN_SYSTEM 4.3). */
export const PLAN_DEADLINE_MS = 30_000;

/** POST /api/v1/trips/plan. Throws ApiError or NetworkError; a caller abort rethrows the AbortError. */
export function planTrip(body: PlanTripRequest, signal?: AbortSignal): Promise<PlanTripResponse> {
  const guarded = AbortSignal.any([
    AbortSignal.timeout(PLAN_DEADLINE_MS),
    ...(signal ? [signal] : []),
  ]);
  return unwrap(() => apiClient.POST("/api/v1/trips/plan", { body, signal: guarded }));
}

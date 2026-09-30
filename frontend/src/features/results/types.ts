import type { components } from "@/services/api-types";

// Generated OpenAPI types under the names the results and map code use. Never hand-written.
type Schemas = components["schemas"];

export type PlanTripResponse = Schemas["PlanTripResponse"];
export type Stop = Schemas["Stop"];
export type StopKind = Schemas["StopKind"];
export type StopCounts = Schemas["StopCounts"];
export type DutyStatus = Schemas["DutyStatus"];
export type Route = Schemas["Route"];
export type RouteLeg = Schemas["RouteLeg"];
export type TimelineEvent = Schemas["TimelineEvent"];
export type TripMeta = Schemas["TripMeta"];
export type TripSummaryData = Schemas["TripSummary"];
export type TripTimezone = Schemas["TimezoneInfo"];
export type TripWarning = Schemas["Warning"];
export type Assumption = Schemas["Assumption"];
export type LogDayRef = Pick<Schemas["LogDay"], "date" | "sheet_index">;

/** Shared by every results panel (DESIGN_SYSTEM 9). Empty and error render nothing here: the empty guidance and the results alert own those. */
export type PanelState<T> =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "error"; message?: string }
  | ({ status: "ready" } & T);

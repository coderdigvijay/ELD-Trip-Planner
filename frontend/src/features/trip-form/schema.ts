import { addDays, compareAsc, format, isValid, parseISO, startOfDay } from "date-fns";
import * as z from "zod/mini";

import type { LocationInput, PlaceInput, PlanTripRequest } from "@/services/trips";

/**
 * Client validation mirrors API_CONTRACT section 7 exactly. Messages reuse the API wording
 * (DESIGN_SYSTEM 4.5 e) so a client error and a server error read the same.
 */

export type LocationValue = LocationInput;

export const LOCATION_MIN = 3;
export const LOCATION_MAX = 200;
export const CYCLE_MAX = 70;
export const CYCLE_STEP = 0.25;
export const DEFAULT_START_TIME = "08:00";
/** Start date window relative to the browser's today (API_CONTRACT 5.1). */
export const START_DAYS_BEFORE = 30;
export const START_DAYS_AFTER = 365;

/** Lower-48 coverage box (API_CONTRACT 5.1). */
const BOX = { latMin: 24.0, latMax: 49.5, lngMin: -125.0, lngMax: -66.5 } as const;

/** Unicode Cc (controls, CR, LF, TAB) and Cf (format: zero-width space, bidi overrides). */
const CONTROL_CHARS = /[\p{Cc}\p{Cf}]/u;
const QUARTER_TIME = /^([01]\d|2[0-3]):(00|15|30|45)$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export const CYCLE_MESSAGE = "Cycle hours must be between 0 and 70, in steps of 0.25.";
export const SAME_PLACE_MESSAGE =
  "Pickup and dropoff are the same place. Choose a different dropoff.";

export const LOG_HEADER_LIMITS = {
  driver_name: 80,
  carrier_name: 100,
  main_office_address: 150,
  home_terminal_address: 150,
  truck_number: 40,
  trailer_number: 40,
  shipping_doc: 60,
  shipper_commodity: 100,
} as const;

export type LogHeaderKey = keyof typeof LOG_HEADER_LIMITS;

export const LOG_HEADER_KEYS = Object.keys(LOG_HEADER_LIMITS) as LogHeaderKey[];

/** NFC, trimmed, inner whitespace collapsed: the server's normalisation. */
export function normalizeText(text: string): string {
  return text.normalize("NFC").replace(/\s+/g, " ").trim();
}

export function isPlaceInput(value: unknown): value is PlaceInput {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.label === "string" &&
    typeof candidate.lat === "number" &&
    typeof candidate.lng === "number"
  );
}

function isLocationValue(value: unknown): value is LocationValue {
  return typeof value === "string" || isPlaceInput(value);
}

export function locationLabel(value: LocationValue): string {
  return typeof value === "string" ? value : value.label;
}

function locationMessage(value: LocationValue): string | null {
  if (typeof value === "string") {
    const text = normalizeText(value);
    if (text.length === 0) return "Enter a place. Pick a suggestion or type City, ST.";
    if (CONTROL_CHARS.test(value.replace(/\s/g, " "))) {
      return "Remove hidden or control characters from this place.";
    }
    if (text.length < LOCATION_MIN) return "Enter at least 3 characters, or pick a suggestion.";
    if (text.length > LOCATION_MAX) return "Use 200 characters or fewer.";
    return null;
  }
  const label = normalizeText(value.label);
  if (label.length === 0) return "Enter a place. Pick a suggestion or type City, ST.";
  if (label.length > LOCATION_MAX) return "Use 200 characters or fewer.";
  if (CONTROL_CHARS.test(value.label.replace(/\s/g, " "))) {
    return "Remove hidden or control characters from this place.";
  }
  const { lat, lng } = value;
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return "This place has no valid coordinates.";
  if (lat < BOX.latMin || lat > BOX.latMax || lng < BOX.lngMin || lng > BOX.lngMax) {
    return "Trips must start, pick up and drop off in the lower 48 states.";
  }
  return null;
}

const locationSchema = z
  .custom<LocationValue>(isLocationValue, {
    error: "Enter a place. Pick a suggestion or type City, ST.",
  })
  .check(
    z.superRefine((value, ctx) => {
      const message = locationMessage(value);
      if (message) ctx.addIssue({ code: "custom", message });
    }),
  );

function isOnCycleGrid(hours: number): boolean {
  return Number.isFinite(hours) && hours >= 0 && hours <= CYCLE_MAX && Number.isInteger(hours * 4);
}

const cycleSchema = z
  .nullable(z.number({ error: CYCLE_MESSAGE }))
  .check(z.refine((hours) => hours !== null && isOnCycleGrid(hours), { error: CYCLE_MESSAGE }));

export function startDateBounds(now: Date = new Date()): { min: string; max: string } {
  const today = startOfDay(now);
  return {
    min: format(addDays(today, -START_DAYS_BEFORE), "yyyy-MM-dd"),
    max: format(addDays(today, START_DAYS_AFTER), "yyyy-MM-dd"),
  };
}

const START_DATE_MESSAGE = "Start date must be within 30 days before and 365 days after today.";

const startDateSchema = z.string().check(
  z.superRefine((value, ctx) => {
    if (value === "") return;
    const parsed = parseISO(value);
    if (!ISO_DATE.test(value) || !isValid(parsed)) {
      ctx.addIssue({ code: "custom", message: "Enter the start date as year, month, day." });
      return;
    }
    const { min, max } = startDateBounds();
    if (compareAsc(parsed, parseISO(min)) < 0 || compareAsc(parsed, parseISO(max)) > 0) {
      ctx.addIssue({ code: "custom", message: START_DATE_MESSAGE });
    }
  }),
);

const startTimeSchema = z.string().check(
  z.refine((value) => QUARTER_TIME.test(value), {
    error: "Start time must be on a quarter hour, like 08:15.",
  }),
);

function headerField(max: number) {
  return z.string().check(
    z.maxLength(max, { error: `Use ${String(max)} characters or fewer.` }),
    z.refine((value) => !CONTROL_CHARS.test(value), {
      error: "Remove hidden or control characters from this field.",
    }),
  );
}

const logHeaderSchema = z.object({
  driver_name: headerField(LOG_HEADER_LIMITS.driver_name),
  carrier_name: headerField(LOG_HEADER_LIMITS.carrier_name),
  main_office_address: headerField(LOG_HEADER_LIMITS.main_office_address),
  home_terminal_address: headerField(LOG_HEADER_LIMITS.home_terminal_address),
  truck_number: headerField(LOG_HEADER_LIMITS.truck_number),
  trailer_number: headerField(LOG_HEADER_LIMITS.trailer_number),
  shipping_doc: headerField(LOG_HEADER_LIMITS.shipping_doc),
  shipper_commodity: headerField(LOG_HEADER_LIMITS.shipper_commodity),
});

/** Equal means equal coordinates at 5 decimals, or equal normalised text ignoring case. */
export function samePlace(a: LocationValue, b: LocationValue): boolean {
  if (typeof a === "string" && typeof b === "string") {
    return normalizeText(a).toLowerCase() === normalizeText(b).toLowerCase();
  }
  if (isPlaceInput(a) && isPlaceInput(b)) {
    return a.lat.toFixed(5) === b.lat.toFixed(5) && a.lng.toFixed(5) === b.lng.toFixed(5);
  }
  return false;
}

export const tripFormSchema = z
  .object({
    current_location: locationSchema,
    pickup_location: locationSchema,
    dropoff_location: locationSchema,
    current_cycle_used_hours: cycleSchema,
    start_date: startDateSchema,
    start_time: startTimeSchema,
    log_header: logHeaderSchema,
  })
  .check(
    z.superRefine((values, ctx) => {
      if (samePlace(values.pickup_location, values.dropoff_location)) {
        ctx.addIssue({ code: "custom", path: ["dropoff_location"], message: SAME_PLACE_MESSAGE });
      }
    }),
  );

export type TripFormValues = z.infer<typeof tripFormSchema>;
export type LocationFieldName = "current_location" | "pickup_location" | "dropoff_location";
export type TripFieldName =
  | LocationFieldName
  | "current_cycle_used_hours"
  | "start_date"
  | "start_time"
  | `log_header.${LogHeaderKey}`;

export const TRIP_FIELD_NAMES: readonly TripFieldName[] = [
  "current_location",
  "pickup_location",
  "dropoff_location",
  "current_cycle_used_hours",
  "start_date",
  "start_time",
  ...LOG_HEADER_KEYS.map((key): TripFieldName => `log_header.${key}`),
];

export function isTripFieldName(name: string): name is TripFieldName {
  return TRIP_FIELD_NAMES.some((known) => known === name);
}

/**
 * Log details start pre-filled with the FMCSA guide's completed sample log (p. 19: John Doe's
 * Transportation, Washington D.C., vehicles 123 and 20544, shipping no. 101601), so a sheet is
 * "filled out" even when the user types only the four trip inputs. Every value is visible and
 * editable in the "Start time and log details" section; clearing a field leaves that line blank.
 */
export function defaultLogHeader(): TripFormValues["log_header"] {
  return {
    driver_name: "John E. Doe",
    carrier_name: "John Doe's Transportation",
    main_office_address: "Washington, D.C.",
    home_terminal_address: "Washington, D.C.",
    truck_number: "123",
    trailer_number: "20544",
    shipping_doc: "101601",
    shipper_commodity: "ACME Foods, dry groceries",
  };
}

export function defaultTripValues(): TripFormValues {
  return {
    current_location: "",
    pickup_location: "",
    dropoff_location: "",
    current_cycle_used_hours: 0,
    start_date: "",
    start_time: DEFAULT_START_TIME,
    log_header: defaultLogHeader(),
  };
}

/** Example trip: long enough for 2+ days, a fuel stop and a 10 hr rest (DESIGN_SYSTEM 4.1). */
export const EXAMPLE_TRIP = {
  current_location: { label: "Richmond, VA", lat: 37.54072, lng: -77.43605 },
  pickup_location: { label: "Chicago, IL", lat: 41.87811, lng: -87.6298 },
  dropoff_location: { label: "Denver, CO", lat: 39.73924, lng: -104.99025 },
  current_cycle_used_hours: 23.5,
} as const satisfies Pick<
  TripFormValues,
  "current_location" | "pickup_location" | "dropoff_location" | "current_cycle_used_hours"
>;

function toLocationInput(value: LocationValue): LocationInput {
  if (typeof value === "string") return normalizeText(value);
  return { label: normalizeText(value.label), lat: value.lat, lng: value.lng };
}

/** Validated form values to the API body. Blank optional fields are omitted (they mean "default"). */
export function toPlanRequest(values: TripFormValues): PlanTripRequest {
  const header: Record<string, string> = {};
  for (const key of LOG_HEADER_KEYS) {
    const text = normalizeText(values.log_header[key]);
    if (text) header[key] = text;
  }
  return {
    current_location: toLocationInput(values.current_location),
    pickup_location: toLocationInput(values.pickup_location),
    dropoff_location: toLocationInput(values.dropoff_location),
    current_cycle_used_hours: values.current_cycle_used_hours ?? 0,
    ...(values.start_date ? { start_date: values.start_date } : {}),
    ...(values.start_time !== DEFAULT_START_TIME ? { start_time: values.start_time } : {}),
    ...(Object.keys(header).length > 0 ? { log_header: header } : {}),
  };
}

export const START_TIME_OPTIONS: readonly string[] = Array.from({ length: 96 }, (_, index) => {
  const hours = String(Math.floor(index / 4)).padStart(2, "0");
  const minutes = String((index % 4) * 15).padStart(2, "0");
  return `${hours}:${minutes}`;
});

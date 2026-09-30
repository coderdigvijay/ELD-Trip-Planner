import {
  defaultTripValues,
  isPlaceInput,
  LOG_HEADER_KEYS,
  tripFormSchema,
  type LocationValue,
  type TripFormValues,
} from "./schema";

/**
 * Share state: the form inputs in one compact `q` param (ARCHITECTURE section 9). It only prefills
 * the form. It is decoded through the same zod schema as typed input; invalid parts are dropped.
 */

type Compact = {
  c?: unknown;
  p?: unknown;
  d?: unknown;
  h?: unknown;
  sd?: unknown;
  st?: unknown;
  lh?: unknown;
};

const PARAM = "q";

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text: string): string {
  const padded = text.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  return new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0)));
}

function packLocation(value: LocationValue): string | [string, number, number] {
  return typeof value === "string" ? value : [value.label, value.lat, value.lng];
}

function unpackLocation(value: unknown): LocationValue | null {
  if (typeof value === "string") return value;
  if (Array.isArray(value) && value.length === 3) {
    const [label, lat, lng] = value as unknown[];
    const place = { label, lat, lng };
    if (isPlaceInput(place)) return place;
  }
  return null;
}

export function encodeShare(values: TripFormValues): string {
  const lh: Record<string, string> = {};
  for (const key of LOG_HEADER_KEYS) {
    if (values.log_header[key].trim()) lh[key] = values.log_header[key];
  }
  const compact: Compact = {
    c: packLocation(values.current_location),
    p: packLocation(values.pickup_location),
    d: packLocation(values.dropoff_location),
    h: values.current_cycle_used_hours,
    ...(values.start_date ? { sd: values.start_date } : {}),
    ...(values.start_time !== defaultTripValues().start_time ? { st: values.start_time } : {}),
    ...(Object.keys(lh).length > 0 ? { lh } : {}),
  };
  return `${PARAM}=${toBase64Url(JSON.stringify(compact))}`;
}

/** Returns prefill values, or null when there is no usable `q`. Never throws. */
export function decodeShare(search: string): TripFormValues | null {
  try {
    const raw = new URLSearchParams(search).get(PARAM);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(fromBase64Url(raw));
    if (typeof parsed !== "object" || parsed === null) return null;
    const compact = parsed as Compact;
    const values = defaultTripValues();
    const c = unpackLocation(compact.c);
    const p = unpackLocation(compact.p);
    const d = unpackLocation(compact.d);
    if (c !== null) values.current_location = c;
    if (p !== null) values.pickup_location = p;
    if (d !== null) values.dropoff_location = d;
    if (typeof compact.h === "number") values.current_cycle_used_hours = compact.h;
    if (typeof compact.sd === "string") values.start_date = compact.sd;
    if (typeof compact.st === "string") values.start_time = compact.st;
    if (typeof compact.lh === "object" && compact.lh !== null) {
      const lh = compact.lh as Record<string, unknown>;
      for (const key of LOG_HEADER_KEYS) {
        const entry = lh[key];
        if (typeof entry === "string") values.log_header[key] = entry;
      }
    }
    return dropInvalid(values);
  } catch {
    return null;
  }
}

/** Reset every field the schema rejects to its default. */
function dropInvalid(values: TripFormValues): TripFormValues | null {
  const defaults = defaultTripValues();
  const result = tripFormSchema.safeParse(values);
  if (result.success) return values;
  const next: TripFormValues = { ...values, log_header: { ...values.log_header } };
  for (const issue of result.error.issues) {
    const [root, child] = issue.path;
    if (root === "log_header" && typeof child === "string") {
      const key = LOG_HEADER_KEYS.find((known) => known === child);
      if (key) next.log_header[key] = defaults.log_header[key];
    } else if (typeof root === "string" && root in defaults && root !== "log_header") {
      const field = root as Exclude<keyof TripFormValues, "log_header">;
      Object.assign(next, { [field]: defaults[field] });
    }
  }
  // Pickup equals dropoff is a pair problem: keep pickup, drop the dropoff.
  return next;
}

export function writeShare(values: TripFormValues): void {
  const url = new URL(window.location.href);
  url.search = encodeShare(values);
  window.history.replaceState(null, "", url);
}

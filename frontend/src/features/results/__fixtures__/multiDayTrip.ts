import polyline from "@mapbox/polyline";

import type { PlanTripResponse, Stop, TimelineEvent } from "../types";

// A three-sheet trip that crosses the US fall-back date (2026-11-01). The offset is frozen at
// -04:00 for the whole trip (A3), so 06:00-04:00 must render as 06:00 even where the browser
// zone has already fallen back to -05:00.

export const LONG_LABEL =
  "near Mount Pleasant Township Industrial Park Distribution Center Access Road, Allegheny County, PA";

const stop = (
  id: string,
  over: Partial<Stop> & Pick<Stop, "kind" | "arrive_at" | "depart_at" | "label" | "lat" | "lng">,
): Stop => ({
  id,
  label_source: "geocoded",
  duration_h: 0,
  duty_status: "on_duty",
  cumulative_mi: 0,
  leg_index: 0,
  note: "",
  reason: "",
  ...over,
});

export const stops: Stop[] = [
  stop("s1", {
    kind: "start",
    label: "Richmond, VA",
    lat: 37.54072,
    lng: -77.43605,
    arrive_at: "2026-10-31T20:00:00-04:00",
    depart_at: "2026-10-31T20:30:00-04:00",
    duration_h: 0.5,
    note: "Pre-trip inspection",
  }),
  stop("s2", {
    kind: "pickup",
    label: "Baltimore, MD",
    lat: 39.29038,
    lng: -76.61219,
    arrive_at: "2026-10-31T23:15:00-04:00",
    depart_at: "2026-11-01T00:15:00-04:00",
    duration_h: 1,
    cumulative_mi: 152.3,
    note: "Pickup",
    reason: "Pickup (1 hr on duty)",
  }),
  stop("s3", {
    kind: "rest",
    label: LONG_LABEL,
    lat: 40.1,
    lng: -79.8,
    arrive_at: "2026-11-01T06:00:00-04:00",
    depart_at: "2026-11-01T16:30:00-04:00",
    duration_h: 10.5,
    duty_status: "sleeper",
    cumulative_mi: 610.2,
    leg_index: 1,
    note: "10-hr rest (sleeper)",
    reason: "10-hr rest: 11 hr driving limit reached",
  }),
  stop("s4", {
    kind: "fuel",
    label: "near Hagerstown, MD",
    label_source: "nearby",
    lat: 39.64,
    lng: -77.72,
    arrive_at: "2026-11-01T18:00:00-04:00",
    depart_at: "2026-11-01T18:30:00-04:00",
    duration_h: 0.5,
    cumulative_mi: 700,
    leg_index: 1,
    note: "Fuel",
    reason: "Fuel: 1,000 mi limit",
  }),
  stop("s5", {
    kind: "dropoff",
    label: "Newark, NJ",
    lat: 40.73566,
    lng: -74.17237,
    arrive_at: "2026-11-02T01:00:00-04:00",
    depart_at: "2026-11-02T02:00:00-04:00",
    duration_h: 1,
    cumulative_mi: 1204.4,
    leg_index: 1,
    note: "Dropoff",
    reason: "Dropoff (1 hr on duty)",
  }),
  stop("s6", {
    kind: "end",
    label: "Newark, NJ",
    lat: 40.73566,
    lng: -74.17237,
    arrive_at: "2026-11-02T02:00:00-04:00",
    depart_at: "2026-11-02T02:00:00-04:00",
    duty_status: "off",
    cumulative_mi: 1204.4,
    leg_index: 1,
    note: "Released from duty",
    reason: "Trip complete",
  }),
];

const drive = (
  start_at: string,
  end_at: string,
  hours: number,
  start_mi: number,
  end_mi: number,
): TimelineEvent => ({
  start_min: 0,
  end_min: Math.round(hours * 60),
  start_at,
  end_at,
  status: "driving",
  stop_id: null,
  start_label: "",
  end_label: "",
  start_mi,
  end_mi,
  note: "Driving",
});

export const timeline: TimelineEvent[] = [
  drive("2026-10-31T20:30:00-04:00", "2026-10-31T23:15:00-04:00", 2.75, 0, 152.3),
  drive("2026-11-01T00:15:00-04:00", "2026-11-01T06:00:00-04:00", 5.75, 152.3, 610.2),
  drive("2026-11-01T16:30:00-04:00", "2026-11-01T18:00:00-04:00", 1.5, 610.2, 700),
  drive("2026-11-01T18:30:00-04:00", "2026-11-02T01:00:00-04:00", 6.5, 700, 1204.4),
];

export const days = [
  { date: "2026-10-31", sheet_index: 1 },
  { date: "2026-11-01", sheet_index: 2 },
  { date: "2026-11-02", sheet_index: 3 },
];

const path = (points: [number, number][]) => polyline.encode(points);

export const plan: PlanTripResponse = {
  trip: {
    places: {
      current: { label: "Richmond, VA", lat: 37.54072, lng: -77.43605, source: "input" },
      pickup: { label: "Baltimore, MD", lat: 39.29038, lng: -76.61219, source: "geocoded" },
      dropoff: { label: "Newark, NJ", lat: 40.73566, lng: -74.17237, source: "input" },
    },
    timezone: {
      name: "America/New_York",
      abbreviation: "EDT",
      utc_offset: "-04:00",
      utc_offset_min: -240,
    },
    start_at: "2026-10-31T20:00:00-04:00",
    cycle_used_start_h: 10,
    log_header: {
      driver_name: "John Doe",
      carrier_name: "John Doe's Transportation",
      main_office_address: "Washington, D.C.",
      home_terminal_address: "Washington, D.C.",
      truck_number: "123",
      trailer_number: "20544",
      shipping_doc: "101601",
      shipper_commodity: "ACME Foods, dry groceries",
    },
    assumptions: [
      {
        id: "A1",
        text: "You are off duty from midnight until the trip starts, with fresh 11- and 14-hour clocks.",
      },
      {
        id: "A3",
        text: "All times use the home terminal's time (Richmond, VA, UTC-04:00) for the whole trip.",
      },
      {
        id: "A17",
        text: "If a due 30-minute break would leave less than 15 minutes of driving in the 14-hour window, the plan takes the 10-hour rest instead.",
      },
    ],
    warnings: [],
  },
  route: {
    profile: "driving-hgv",
    distance_mi: 1204.4,
    planned_driving_h: 16.5,
    bounds: { south: 37.54072, west: -79.8, north: 40.73566, east: -74.17237 },
    legs: [
      {
        index: 0,
        from_label: "Richmond, VA",
        to_label: "Baltimore, MD",
        distance_mi: 152.3,
        duration_h: 2.62,
        planned_driving_h: 2.75,
        polyline: path([
          [37.54072, -77.43605],
          [38.4, -77.1],
          [39.29038, -76.61219],
        ]),
        bounds: { south: 37.54072, west: -77.43605, north: 39.29038, east: -76.61219 },
      },
      {
        index: 1,
        from_label: "Baltimore, MD",
        to_label: "Newark, NJ",
        distance_mi: 1052.1,
        duration_h: 13.4,
        planned_driving_h: 13.75,
        polyline: path([
          [39.29038, -76.61219],
          [39.64, -77.72],
          [40.1, -79.8],
          [40.4, -76.5],
          [40.73566, -74.17237],
        ]),
        bounds: { south: 39.29038, west: -79.8, north: 40.73566, east: -74.17237 },
      },
    ],
  },
  stops,
  timeline,
  days: [],
  summary: {
    total_distance_mi: 1204.4,
    driving_h: 16.5,
    on_duty_not_driving_h: 3,
    on_duty_total_h: 19.5,
    trip_duration_h: 54.0,
    arrival_at: "2026-11-02T01:00:00-04:00",
    released_at: "2026-11-02T02:00:00-04:00",
    sheet_count: 3,
    cycle_used_start_h: 10,
    cycle_used_end_h: 29.5,
    counts: { fuel: 1, break: 0, rest: 1, restart: 0 },
  },
};

/** Test helper: a value that must exist (keeps tests free of non-null assertions). */
export function must<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("expected a value");
  return value;
}

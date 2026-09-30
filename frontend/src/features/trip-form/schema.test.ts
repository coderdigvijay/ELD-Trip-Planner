import { addDays, format } from "date-fns";

import {
  CYCLE_MESSAGE,
  defaultTripValues,
  EXAMPLE_TRIP,
  normalizeText,
  SAME_PLACE_MESSAGE,
  START_TIME_OPTIONS,
  toPlanRequest,
  tripFormSchema,
  type TripFormValues,
} from "./schema";

function valid(overrides: Partial<TripFormValues> = {}): TripFormValues {
  return {
    ...defaultTripValues(),
    current_location: "Richmond, VA",
    pickup_location: "Chicago, IL",
    dropoff_location: "Denver, CO",
    ...overrides,
  };
}

function messages(values: TripFormValues): Record<string, string> {
  const result = tripFormSchema.safeParse(values);
  if (result.success) return {};
  return Object.fromEntries(result.error.issues.map((i) => [i.path.join("."), i.message]));
}

describe("cycle hours", () => {
  it.each([0, 70, 69.75, 23.5, 0.25])("accepts %s", (hours) => {
    expect(messages(valid({ current_cycle_used_hours: hours }))).toEqual({});
  });

  it.each([-1, 70.25, 12.3, 71, Number.NaN, null])(
    "rejects %s with the contract wording",
    (hours) => {
      expect(messages(valid({ current_cycle_used_hours: hours })).current_cycle_used_hours).toBe(
        CYCLE_MESSAGE,
      );
    },
  );
});

describe("locations", () => {
  it("accepts 3 and 200 character text", () => {
    expect(messages(valid({ current_location: "abc" }))).toEqual({});
    expect(messages(valid({ current_location: "a".repeat(200) }))).toEqual({});
  });

  it("rejects short, long and empty text", () => {
    expect(messages(valid({ current_location: "ab" })).current_location).toBe(
      "Enter at least 3 characters, or pick a suggestion.",
    );
    expect(messages(valid({ current_location: "a".repeat(201) })).current_location).toMatch(/200/);
    expect(messages(valid({ current_location: "   " })).current_location).toMatch(/Enter a place/);
  });

  it("rejects control and zero-width characters", () => {
    expect(messages(valid({ current_location: "Rich​mond" })).current_location).toMatch(/hidden/);
    expect(messages(valid({ current_location: "Rich\u0007mond" })).current_location).toMatch(
      /hidden/,
    );
  });

  it("treats line breaks as whitespace for length but rejects other controls", () => {
    expect(normalizeText("  Rich   mond \n")).toBe("Rich mond");
  });

  it("rejects a picked place outside the lower 48", () => {
    const alaska = { label: "Anchorage, AK", lat: 61.2, lng: -149.9 };
    expect(messages(valid({ current_location: alaska })).current_location).toMatch(/lower 48/);
  });

  it("rejects pickup equal to dropoff, ignoring case and comparing coordinates", () => {
    expect(
      messages(valid({ pickup_location: "Denver, CO", dropoff_location: " denver,  co" }))
        .dropoff_location,
    ).toBe(SAME_PLACE_MESSAGE);
    const a = { label: "A", lat: 39.73924, lng: -104.99025 };
    const b = { label: "B", lat: 39.739241, lng: -104.990249 };
    expect(messages(valid({ pickup_location: a, dropoff_location: b })).dropoff_location).toBe(
      SAME_PLACE_MESSAGE,
    );
  });

  it("allows current equal to pickup or dropoff", () => {
    expect(messages(valid({ pickup_location: "Richmond, VA" }))).toEqual({});
    expect(messages(valid({ dropoff_location: "Richmond, VA" }))).toEqual({});
  });
});

describe("optional details", () => {
  const today = new Date();
  const day = (offset: number) => format(addDays(today, offset), "yyyy-MM-dd");

  it("accepts blank and in-window dates, rejects outside the window", () => {
    expect(messages(valid({ start_date: "" }))).toEqual({});
    expect(messages(valid({ start_date: day(-30) }))).toEqual({});
    expect(messages(valid({ start_date: day(365) }))).toEqual({});
    expect(messages(valid({ start_date: day(-31) })).start_date).toBeDefined();
    expect(messages(valid({ start_date: day(366) })).start_date).toBeDefined();
    expect(messages(valid({ start_date: "2026-02-30" })).start_date).toBeDefined();
  });

  it("offers only quarter hours, 96 of them", () => {
    expect(START_TIME_OPTIONS).toHaveLength(96);
    expect(START_TIME_OPTIONS[0]).toBe("00:00");
    expect(START_TIME_OPTIONS.at(-1)).toBe("23:45");
    expect(messages(valid({ start_time: "08:10" })).start_time).toBeDefined();
    expect(messages(valid({ start_time: "24:00" })).start_time).toBeDefined();
  });

  it("enforces the log header length limits", () => {
    const header = {
      ...defaultTripValues().log_header,
      driver_name: "x".repeat(81),
      truck_number: "y".repeat(40),
    };
    const result = messages(valid({ log_header: header }));
    expect(result["log_header.driver_name"]).toMatch(/80/);
    expect(result["log_header.truck_number"]).toBeUndefined();
  });
});

describe("toPlanRequest", () => {
  it("omits blank optionals and sends picked places with coordinates", () => {
    const body = toPlanRequest(valid({ ...EXAMPLE_TRIP }));
    expect(body).toEqual({
      current_location: EXAMPLE_TRIP.current_location,
      pickup_location: EXAMPLE_TRIP.pickup_location,
      dropoff_location: EXAMPLE_TRIP.dropoff_location,
      current_cycle_used_hours: 23.5,
    });
  });

  it("sends free text trimmed, and only changed optional fields", () => {
    const body = toPlanRequest(
      valid({
        current_location: "  Richmond,   VA ",
        start_date: "2026-10-05",
        start_time: "09:15",
        log_header: { ...defaultTripValues().log_header, driver_name: " John Doe " },
      }),
    );
    expect(body).toMatchObject({
      current_location: "Richmond, VA",
      start_date: "2026-10-05",
      start_time: "09:15",
      log_header: { driver_name: "John Doe" },
    });
  });
});

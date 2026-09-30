import { ApiError, NetworkError } from "@/services/errors";

import { describePlanError, toFormField, type AlertFailure } from "./describeError";

const api = (code: string, extra: Partial<ConstructorParameters<typeof ApiError>[0]> = {}) =>
  new ApiError({ code, message: "server words", status: 422, requestId: "abc123", ...extra });

function alertOf(error: unknown): AlertFailure {
  const failure = describePlanError(error);
  if (failure.kind !== "alert") throw new Error("expected an alert");
  return failure;
}

describe("toFormField", () => {
  it("maps dotted location paths to their root and keeps log header paths", () => {
    expect(toFormField("pickup_location.lat")).toBe("pickup_location");
    expect(toFormField("log_header.driver_name")).toBe("log_header.driver_name");
    expect(toFormField("q")).toBeNull();
    expect(toFormField(undefined)).toBeNull();
  });
});

describe("field errors", () => {
  it.each(["LOCATION_NOT_FOUND", "UNSUPPORTED_LOCATION", "AMBIGUOUS_LOCATION"])(
    "%s lands under the named field with the server message",
    (code) => {
      const failure = describePlanError(api(code, { field: "dropoff_location" }));
      expect(failure).toEqual({
        kind: "fields",
        problems: [{ field: "dropoff_location", message: "server words" }],
      });
    },
  );

  it("VALIDATION_ERROR marks every detail", () => {
    const failure = describePlanError(
      api("VALIDATION_ERROR", {
        status: 400,
        details: [
          { field: "current_cycle_used_hours", message: "one" },
          { field: "start_time", message: "two" },
        ],
      }),
    );
    expect(failure).toMatchObject({ kind: "fields" });
    expect(failure.kind === "fields" && failure.problems.map((p) => p.field)).toEqual([
      "current_cycle_used_hours",
      "start_time",
    ]);
  });

  it("VALIDATION_ERROR with no field falls back to an alert", () => {
    expect(alertOf(api("VALIDATION_ERROR", { status: 400 })).action).toEqual({
      type: "retry",
      countdownS: null,
    });
  });
});

describe("results alerts", () => {
  it("ROUTE_NOT_FOUND edits the named leg", () => {
    const failure = alertOf(api("ROUTE_NOT_FOUND", { field: "dropoff_location" }));
    expect(failure).toMatchObject({
      title: "No drivable route found",
      body: "server words",
      action: { type: "edit", field: "dropoff_location", label: "Edit dropoff" },
    });
    expect(alertOf(api("ROUTE_NOT_FOUND")).action).toMatchObject({
      label: "Edit locations",
      field: "current_location",
    });
  });

  it("TRIP_TOO_LONG offers Edit locations", () => {
    expect(alertOf(api("TRIP_TOO_LONG")).action).toMatchObject({ label: "Edit locations" });
  });

  it("RATE_LIMITED is a warning with a countdown from retry_after_s, fallback 60", () => {
    expect(alertOf(api("RATE_LIMITED", { retryAfterS: 42 }))).toMatchObject({
      tone: "warn",
      action: { type: "retry", countdownS: 42 },
    });
    expect(alertOf(api("RATE_LIMITED")).action).toEqual({ type: "retry", countdownS: 60 });
  });

  it("UPSTREAM_QUOTA_EXCEEDED counts down only when the wait is 300 s or less", () => {
    expect(alertOf(api("UPSTREAM_QUOTA_EXCEEDED", { retryAfterS: 30 })).action).toEqual({
      type: "retry",
      countdownS: 30,
    });
    expect(alertOf(api("UPSTREAM_QUOTA_EXCEEDED")).action).toEqual({ type: "none" });
    expect(alertOf(api("UPSTREAM_QUOTA_EXCEEDED", { retryAfterS: 900 })).action).toEqual({
      type: "none",
    });
  });

  it("UPSTREAM_UNAVAILABLE uses the UI's own body", () => {
    expect(alertOf(api("UPSTREAM_UNAVAILABLE", { status: 503 })).body).toMatch(/routing provider/);
  });

  it.each(["INTERNAL", "NOT_FOUND", "METHOD_NOT_ALLOWED", "SOMETHING_NEW"])(
    "%s gets the unexpected error with the request id",
    (code) => {
      expect(alertOf(api(code, { status: 500 }))).toMatchObject({
        title: "The planner hit an unexpected error",
        requestId: "abc123",
        action: { type: "retry", countdownS: null },
      });
    },
  );

  it("no response is Could not reach the server", () => {
    expect(alertOf(new NetworkError("offline"))).toMatchObject({
      title: "Could not reach the server",
      body: "Check your connection and try again.",
    });
  });

  it("branches on code, never on message text", () => {
    const a = alertOf(api("INTERNAL", { message: "Wait 42 seconds" }));
    expect(a.title).toBe("The planner hit an unexpected error");
  });
});

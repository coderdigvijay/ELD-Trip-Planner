import type { LogDay, LogSegment } from "../types";

// A repeating long-haul day (rest, pre-trip, drive, fuel, drive, rest). Test data only: it exercises
// pixel mapping for many sheets and is not an HOS-valid plan.
const PLACES = [
  "Chicago, IL",
  "Des Moines, IA",
  "Omaha, NE",
  "North Platte, NE",
  "Denver, CO",
  "Grand Junction, UT",
  "Salt Lake City, UT",
  "Boise, ID",
];

const s = (
  start_min: number,
  end_min: number,
  status: LogSegment["status"],
  location_label: string,
  note: string,
  stop_id: string | null,
): LogSegment => ({
  start_min,
  end_min,
  status,
  location_label,
  note,
  stationary: stop_id !== null,
  stop_id,
});

export function longHaulDays(count: number): LogDay[] {
  return Array.from({ length: count }, (_, i): LogDay => {
    const here = PLACES[i % PLACES.length] ?? "";
    const there = PLACES[(i + 1) % PLACES.length] ?? "";
    const date = `2026-11-${String(2 + i).padStart(2, "0")}`;
    return {
      date,
      sheet_index: i + 1,
      from_label: here,
      to_label: there,
      miles_driven: 612.4,
      segments: [
        s(0, 390, "sleeper", here, "10-hr rest (sleeper)", `r${i}`),
        s(390, 420, "on_duty", here, "Pre-trip inspection", `r${i}`),
        s(420, 720, "driving", there, "Driving", null),
        s(720, 750, "on_duty", there, "Fuel", `f${i}`),
        s(750, 1050, "driving", there, "Driving", null),
        s(1050, 1440, "sleeper", there, "10-hr rest (sleeper)", `r${i + 1}`),
      ],
      remarks: [
        { minute: 390, location_label: here, note: "Pre-trip inspection" },
        { minute: 420, location_label: here, note: "Driving" },
        { minute: 720, location_label: there, note: "Fuel" },
        { minute: 750, location_label: there, note: "Driving" },
        { minute: 1050, location_label: there, note: "10-hr rest (sleeper)" },
      ],
      totals: { off: 0, sleeper: 13, driving: 10, on_duty: 1 },
      recap: {
        on_duty_today: 11,
        a_last7: 11 * (i + 1),
        b_available_tomorrow: Math.max(0, 70 - 11 * (i + 1)),
        c_last8: 11 * (i + 1),
        restart_note: null,
      },
    };
  });
}

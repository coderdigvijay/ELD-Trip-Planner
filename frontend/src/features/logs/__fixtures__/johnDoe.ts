import type { LogDay, LogHeader, LogSegment, TripTimezone } from "../types";

// FMCSA Driver's Guide pp. 18-19 (docs/research/hos-domain.md section 5), in the API day shape.
const seg = (
  start_min: number,
  end_min: number,
  status: LogSegment["status"],
  location_label: string,
  note: string,
  stationary: boolean,
): LogSegment => ({
  start_min,
  end_min,
  status,
  location_label,
  note,
  stationary,
  stop_id: stationary ? `s${start_min}` : null,
});

export const johnDoeHeader: LogHeader = {
  driver_name: "John E. Doe",
  carrier_name: "John Doe's Transportation",
  main_office_address: "Washington, D.C.",
  home_terminal_address: "Washington, D.C.",
  truck_number: "123",
  trailer_number: "20544",
  shipping_doc: "101601",
  shipper_commodity: "",
};

export const johnDoeTimezone: TripTimezone = {
  name: "America/New_York",
  abbreviation: "EDT",
  utc_offset: "-04:00",
  utc_offset_min: -240,
};

export const johnDoeDay: LogDay = {
  date: "2021-04-09",
  sheet_index: 1,
  from_label: "Richmond, VA",
  to_label: "Newark, NJ",
  miles_driven: 350,
  segments: [
    seg(0, 360, "off", "Richmond, VA", "Off duty", false),
    seg(360, 450, "on_duty", "Richmond, VA", "Pre-trip inspection", true),
    seg(450, 540, "driving", "Fredericksburg, VA", "Driving", false),
    seg(540, 570, "on_duty", "Fredericksburg, VA", "Fuel", true),
    seg(570, 720, "driving", "Baltimore, MD", "Driving", false),
    seg(720, 780, "off", "Baltimore, MD", "Lunch", true),
    seg(780, 900, "driving", "Philadelphia, PA", "Driving", false),
    seg(900, 930, "on_duty", "Philadelphia, PA", "Delivery", true),
    seg(930, 960, "driving", "Cherry Hill, NJ", "Driving", false),
    seg(960, 1065, "sleeper", "Cherry Hill, NJ", "Sleeper berth", true),
    seg(1065, 1140, "driving", "Newark, NJ", "Driving", false),
    seg(1140, 1260, "on_duty", "Newark, NJ", "Post-trip, paperwork", true),
    seg(1260, 1440, "off", "Newark, NJ", "Off duty", false),
  ],
  remarks: [
    { minute: 360, location_label: "Richmond, VA", note: "Pre-trip inspection" },
    { minute: 450, location_label: "Richmond, VA", note: "Driving" },
    { minute: 540, location_label: "Fredericksburg, VA", note: "Fuel" },
    { minute: 570, location_label: "Fredericksburg, VA", note: "Driving" },
    { minute: 720, location_label: "Baltimore, MD", note: "Lunch" },
    { minute: 780, location_label: "Baltimore, MD", note: "Driving" },
    { minute: 900, location_label: "Philadelphia, PA", note: "Delivery" },
    { minute: 930, location_label: "Philadelphia, PA", note: "Driving" },
    { minute: 960, location_label: "Cherry Hill, NJ", note: "Sleeper berth" },
    { minute: 1065, location_label: "Cherry Hill, NJ", note: "Driving" },
    { minute: 1140, location_label: "Newark, NJ", note: "Post-trip, paperwork" },
    { minute: 1260, location_label: "Newark, NJ", note: "Off duty" },
  ],
  totals: { off: 10, sleeper: 1.75, driving: 7.75, on_duty: 4.5 },
  recap: {
    on_duty_today: 12.25,
    a_last7: 12.25,
    b_available_tomorrow: 57.75,
    c_last8: 12.25,
    restart_note: null,
  },
};

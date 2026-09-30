import { bracketPath, brackets, dutyPath, segmentIssues, type BracketSpan } from "./geometry";
import {
  fitMono,
  formatHM,
  formatHours,
  formatLongDate,
  formatMiles,
  splitDate,
  truncate,
  type DateParts,
  type FittedText,
} from "./format";
import { layoutRemarks, type RemarkLayout } from "./layoutRemarks";
import type { LogDay, LogHeader, TripTimezone } from "./types";

// Everything the sheet draws, computed once per day. Pure: no DOM reads, no HOS math (LOG_SHEET_RENDER_SPEC 5.6).

export interface FieldText extends FittedText {
  /** Full untruncated value, for <title> and the table view. */
  full: string;
}

const RESTART_CHARS = 14;
const RESTART_LINES = 5;
const TOTAL_TOLERANCE = 0.01;

function field(value: string, maxWidth: number, size: number, minSize?: number): FieldText {
  return { ...fitMono(value, maxWidth, size, minSize), full: value };
}

/** Greedy word wrap at a fixed character count; anything past `maxLines` is cut with "...". */
export function wrapChars(text: string, perLine: number, maxLines: number): string[] {
  const lines: string[] = [];
  let current = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    let rest = word;
    while (rest.length > perLine) {
      if (current) {
        lines.push(current);
        current = "";
      }
      lines.push(rest.slice(0, perLine));
      rest = rest.slice(perLine);
    }
    if (!current) current = rest;
    else if (current.length + 1 + rest.length <= perLine) current = `${current} ${rest}`;
    else {
      lines.push(current);
      current = rest;
    }
  }
  if (current) lines.push(current);
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  kept[maxLines - 1] = truncate(`${kept[maxLines - 1] ?? ""}${lines[maxLines] ?? ""}`, perLine);
  return kept;
}

export interface SheetModel {
  problems: string[];
  date: DateParts;
  title: string;
  summary: string;
  dutyD: string;
  bracketSpans: BracketSpan[];
  bracketD: string;
  remarks: RemarkLayout;
  from: FieldText;
  to: FieldText;
  miles: string;
  vehicle: FieldText;
  driver: FieldText;
  carrier: FieldText;
  mainOffice: FieldText;
  homeTerminal: FieldText;
  shippingDoc: FieldText;
  shipper: FieldText;
  rowTotals: { off: string; sleeper: string; driving: string; on_duty: string };
  grandTotal: string;
  recap: {
    today: string;
    a: string;
    b: string;
    c: string;
    restartLines: string[];
    restartFull: string | null;
  };
  timeBase: string | null;
}

export function sheetProblems(day: LogDay): string[] {
  const problems: string[] = [];
  const kinds = new Set(segmentIssues(day.segments).map((i) => i.kind));
  if (kinds.size > 0)
    problems.push(`segments are not contiguous over 00:00 to 24:00 (${[...kinds].join(", ")})`);
  if (day.remarks.some((r) => r.minute < 0 || r.minute > 1439))
    problems.push("a remark is outside 00:00 to 23:59");
  const t = day.totals;
  const sum = t.off + t.sleeper + t.driving + t.on_duty;
  if (Math.abs(sum - 24) > TOTAL_TOLERANCE)
    problems.push(`totals add up to ${formatHours(sum)}, not 24`);
  return problems;
}

export function buildSheetModel(
  day: LogDay,
  header: LogHeader,
  timezone?: TripTimezone,
): SheetModel {
  const problems = sheetProblems(day);
  if (problems.length > 0 && import.meta.env.DEV) {
    console.error(`Log sheet ${day.date}: ${problems.join("; ")}`);
  }
  const t = day.totals;
  const grand = t.off + t.sleeper + t.driving + t.on_duty;
  const restartFull = day.recap.restart_note;
  return {
    problems,
    date: splitDate(day.date),
    title: formatLongDate(day.date),
    summary: `Off ${formatHM(t.off)} · Sleeper ${formatHM(t.sleeper)} · Driving ${formatHM(t.driving)} · On duty ${formatHM(t.on_duty)} · Total ${formatHM(grand)}`,
    dutyD: dutyPath(day.segments),
    bracketSpans: brackets(day.segments),
    bracketD: bracketPath(brackets(day.segments)),
    remarks: layoutRemarks(day.remarks, day.segments),
    from: field(day.from_label, 358, 15),
    to: field(day.to_label, 392, 15),
    miles: formatMiles(day.miles_driven),
    vehicle: field(
      [header.truck_number, header.trailer_number].filter(Boolean).join(", "),
      310,
      15,
    ),
    driver: field(header.driver_name, 480, 15),
    carrier: field(header.carrier_name, 480, 15),
    mainOffice: field(header.main_office_address, 480, 15),
    homeTerminal: field(header.home_terminal_address, 480, 15),
    shippingDoc: field(header.shipping_doc, 150, 13, 11),
    shipper: field(header.shipper_commodity, 150, 13, 11),
    rowTotals: {
      off: formatHours(t.off),
      sleeper: formatHours(t.sleeper),
      driving: formatHours(t.driving),
      on_duty: formatHours(t.on_duty),
    },
    grandTotal: `=${formatHours(grand)}`,
    recap: {
      today: formatHours(day.recap.on_duty_today),
      a: formatHours(day.recap.a_last7),
      b: restartFull !== null ? "70*" : formatHours(day.recap.b_available_tomorrow),
      c: formatHours(day.recap.c_last8),
      restartLines:
        restartFull !== null ? wrapChars(restartFull, RESTART_CHARS, RESTART_LINES) : [],
      restartFull,
    },
    timeBase: timezone
      ? `Home terminal time: ${timezone.abbreviation} (UTC${timezone.utc_offset})`
      : null,
  };
}

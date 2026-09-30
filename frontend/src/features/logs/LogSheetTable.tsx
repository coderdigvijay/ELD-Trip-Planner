import { useId } from "react";

import { STATUS_ORDER, STATUS_TERM } from "./layout";
import { formatClock, formatHours, splitDate } from "./format";
import type { LogDay, TripTimezone } from "./types";

// Text alternative for the sheet (LOG_SHEET_RENDER_SPEC 5.5): every segment, remark, total and recap value.

const th =
  "border-b border-rule bg-surface-sunk px-2 py-1 text-left text-xs font-semibold text-ink-2";
const td = "border-b border-rule px-2 py-1 align-top text-sm text-ink";
const num = "font-mono num";
const caption = "pb-1 text-left text-sm font-semibold text-ink";

export interface LogSheetTableProps {
  day: LogDay;
  timezone?: TripTimezone;
  /** Open the disclosure (used when the sheet could not be drawn). */
  forceOpen?: boolean;
}

export function LogSheetTable({ day, timezone, forceOpen = false }: LogSheetTableProps) {
  const uid = useId();
  const { mm, dd, yyyy } = splitDate(day.date);
  const zone = timezone ? ` (${timezone.abbreviation})` : "";
  const t = day.totals;
  const grand = t.off + t.sleeper + t.driving + t.on_duty;
  const restart = day.recap.restart_note;

  return (
    <details className="log-table group mt-4 print:hidden" open={forceOpen || undefined}>
      <summary className="min-h-6 w-fit cursor-pointer rounded-sm py-1 text-base font-semibold text-pen underline underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
        Show table
      </summary>
      <div className="mt-3 flex flex-col gap-6">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] border-collapse">
            <caption
              className={caption}
            >{`Duty status changes, ${mm}/${dd}/${yyyy}${zone}`}</caption>
            <thead>
              <tr>
                {["Start", "End", "Status", "Hours", "Location", "Note"].map((h) => (
                  <th key={h} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {day.segments.map((s) => (
                <tr key={`${s.start_min}-${s.end_min}`}>
                  <td className={`${td} ${num}`}>{formatClock(s.start_min)}</td>
                  <td className={`${td} ${num}`}>{formatClock(s.end_min)}</td>
                  <td className={td}>{STATUS_TERM[s.status]}</td>
                  <td className={`${td} ${num}`}>{formatHours((s.end_min - s.start_min) / 60)}</td>
                  <td className={td}>{s.location_label}</td>
                  <td className={td}>{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[26rem] border-collapse">
            <caption className={caption}>Remarks</caption>
            <thead>
              <tr>
                {["Time", "Place", "Note"].map((h) => (
                  <th key={h} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {day.remarks.map((r) => (
                <tr key={`${r.minute}-${r.note}`}>
                  <td className={`${td} ${num}`}>{formatClock(r.minute)}</td>
                  <td className={td}>{r.location_label}</td>
                  <td className={td}>{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full max-w-sm border-collapse">
            <caption className={caption}>Total hours</caption>
            <thead>
              <tr>
                <th scope="col" className={th}>
                  Line
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Hours
                </th>
              </tr>
            </thead>
            <tbody>
              {STATUS_ORDER.map((status, i) => (
                <tr key={status}>
                  <th
                    scope="row"
                    className={`${td} text-left font-normal`}
                  >{`${i + 1}. ${STATUS_TERM[status]}`}</th>
                  <td className={`${td} ${num} text-right`}>{formatHours(t[status])}</td>
                </tr>
              ))}
              <tr>
                <th scope="row" className={`${td} text-left font-semibold`}>
                  Total
                </th>
                <td className={`${td} ${num} text-right font-semibold`}>{formatHours(grand)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div role="group" aria-labelledby={`${uid}-recap`}>
          <h3 id={`${uid}-recap`} className={caption}>
            Recap, complete at end of day
          </h3>
          <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <dt className="text-ink-2">On duty hours today</dt>
            <dd className={num}>{formatHours(day.recap.on_duty_today)}</dd>
            <dt className="text-ink-2">A. On duty, last 7 days</dt>
            <dd className={num}>{formatHours(day.recap.a_last7)}</dd>
            <dt className="text-ink-2">B. Available tomorrow (70 hr)</dt>
            <dd className={num}>
              {restart !== null
                ? "70* (34 hr restart in progress; 70 hours available when it completes)"
                : formatHours(day.recap.b_available_tomorrow)}
              {restart !== null ? <span className="block font-sans">{restart}</span> : null}
            </dd>
            <dt className="text-ink-2">C. On duty, last 8 days</dt>
            <dd className={num}>{formatHours(day.recap.c_last8)}</dd>
            <dt className="text-ink-2">60 hr / 7 day side</dt>
            <dd>Not applicable</dd>
          </dl>
        </div>
      </div>
    </details>
  );
}

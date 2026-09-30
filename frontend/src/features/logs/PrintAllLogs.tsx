import { forwardRef } from "react";

import { LogSheet } from "./LogSheet";
import type { LogDay, LogHeader, TripTimezone } from "./types";

export interface PrintAllLogsProps {
  days: readonly LogDay[];
  header: LogHeader;
  sheetCount: number;
  timezone?: TripTimezone;
}

/** Every sheet, one per printed page. Mounted only while printing or exporting; hidden on screen. */
export const PrintAllLogs = forwardRef<HTMLDivElement, PrintAllLogsProps>(function PrintAllLogs(
  { days, header, sheetCount, timezone },
  ref,
) {
  return (
    <div ref={ref} className="log-print-only" data-testid="print-all-logs">
      {days.map((day) => (
        <div key={day.sheet_index} className="log-sheet-page">
          <LogSheet day={day} header={header} sheetCount={sheetCount} timezone={timezone} />
        </div>
      ))}
    </div>
  );
});

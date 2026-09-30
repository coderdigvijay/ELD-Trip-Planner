import { forwardRef } from "react";
import { createPortal } from "react-dom";

import { LogSheet } from "./LogSheet";
import type { LogDay, LogHeader, TripTimezone } from "./types";

export interface PrintAllLogsProps {
  days: readonly LogDay[];
  header: LogHeader;
  sheetCount: number;
  timezone?: TripTimezone;
}

/**
 * Every sheet, one per printed page. Mounted only while printing or exporting; hidden on screen.
 * Portaled to <body> so the print stylesheet can hide the whole app (`#root`) and no card border,
 * padding or shell gutter reaches the paper.
 */
export const PrintAllLogs = forwardRef<HTMLDivElement, PrintAllLogsProps>(function PrintAllLogs(
  { days, header, sheetCount, timezone },
  ref,
) {
  return createPortal(
    <div ref={ref} className="log-print-only" data-testid="print-all-logs">
      {days.map((day) => (
        <div key={day.sheet_index} className="log-sheet-page">
          <LogSheet day={day} header={header} sheetCount={sheetCount} timezone={timezone} />
        </div>
      ))}
    </div>,
    document.body,
  );
});

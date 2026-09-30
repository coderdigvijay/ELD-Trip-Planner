import { Download, Printer } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LogNotice, LogSheetSkeleton } from "./LogSheetStates";
import { EmptyLogs, LogsSection } from "./LogsSection";
import { LogSheet } from "./LogSheet";
import { LogSheetTable } from "./LogSheetTable";
import { LogSheetTabPanel, LogSheetTabs } from "./LogSheetTabs";
import { PrintAllLogs } from "./PrintAllLogs";
import { exportLogsPdf } from "./exportLogsPdf";
import { formatHM } from "./format";
import { x } from "./geometry";
import { VIEW_W } from "./layout";
import { sheetProblems } from "./sheetModel";
import { whenSheetsPainted } from "./printReady";
import { useDayParam } from "./useDayParam";
import { useElementWidth } from "./useElementWidth";
import type { LogDay, LogHeader, TripTimezone } from "./types";
import "./logs.css";

/** Below this container width the sheet keeps a fixed 960 px inside a scroll region (spec 1.1). */
const FLUID_MIN_WIDTH = 900;
const SCROLL_SHEET_WIDTH = 960;
const SHEET_MAX_WIDTH = 1200;

export type DailyLogsState =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "error"; message: string; onRetry?: () => void }
  | {
      status: "ready";
      days: readonly LogDay[];
      header: LogHeader;
      sheetCount: number;
      timezone?: TripTimezone;
    };

/** Ask the logs to show a moment on a sheet (a stop selected on the map or timeline). */
export interface LogFocus {
  sheetIndex: number;
  minute: number;
  /** Change the nonce to re-trigger for the same stop. */
  nonce: number;
}

export interface DailyLogsProps {
  state: DailyLogsState;
  focus?: LogFocus;
  className?: string;
}

export function DailyLogs({ state, focus, className }: DailyLogsProps) {
  return (
    <LogsSection className={className}>
      {state.status === "loading" ? <LogSheetSkeleton /> : null}
      {state.status === "empty" ? <EmptyLogs /> : null}
      {state.status === "error" ? (
        <ErrorLogs message={state.message} onRetry={state.onRetry} />
      ) : null}
      {state.status === "ready" ? (
        <ReadyLogs
          days={state.days}
          header={state.header}
          sheetCount={state.sheetCount}
          timezone={state.timezone}
          focus={focus}
        />
      ) : null}
    </LogsSection>
  );
}

function ErrorLogs({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3">
      <LogNotice>
        <p className="font-semibold">The log sheets could not be shown.</p>
        <p className="text-ink-2">{message}</p>
      </LogNotice>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

interface ReadyProps {
  days: readonly LogDay[];
  header: LogHeader;
  sheetCount: number;
  timezone?: TripTimezone;
  focus?: LogFocus;
}

type PdfState = "idle" | "preparing" | "error";

function ReadyLogs({ days, header, sheetCount, timezone, focus }: ReadyProps) {
  const summaryId = useId();
  const [dayNumber, setDay] = useDayParam(days.length, days);
  const day = days.find((d) => d.sheet_index === dayNumber) ?? days[0];

  const measureRef = useRef<HTMLDivElement>(null);
  const regionRef = useRef<HTMLDivElement>(null);
  const width = useElementWidth(measureRef);
  const scrollMode = width !== null && width < FLUID_MIN_WIDTH;
  const [fit, setFit] = useState(false);
  const fixedWidth = scrollMode && !fit;

  // Printing and PDF export mount every sheet; the live tab shows one.
  const [printAll, setPrintAll] = useState(false);
  const printRequested = useRef(false);
  const [pdf, setPdf] = useState<PdfState>("idle");
  const printRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const before = () => {
      flushSync(() => {
        setPrintAll(true);
      });
    };
    const after = () => {
      setPrintAll(false);
    };
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);

  useEffect(() => {
    if (!printAll || !printRequested.current) return;
    printRequested.current = false;
    const run = { cancelled: false };
    void whenSheetsPainted().then(() => {
      if (!run.cancelled) window.print();
    });
    return () => {
      run.cancelled = true;
    };
  }, [printAll]);

  useEffect(() => {
    if (pdf !== "preparing" || !printAll) return;
    const run = { cancelled: false };
    void (async () => {
      try {
        await whenSheetsPainted();
        const sheets = Array.from(
          printRef.current?.querySelectorAll<SVGSVGElement>(".log-sheet-page svg") ?? [],
        );
        await exportLogsPdf(sheets, { filename: `eld-logs-${days[0]?.date ?? "trip"}.pdf` });
        if (!run.cancelled) setPdf("idle");
      } catch (error) {
        if (import.meta.env.DEV) console.error(error);
        if (!run.cancelled) setPdf("error");
      } finally {
        if (!run.cancelled) setPrintAll(false);
      }
    })();
    return () => {
      run.cancelled = true;
    };
  }, [pdf, printAll, days]);

  // A new plan starts at the left edge.
  useEffect(() => {
    if (regionRef.current) regionRef.current.scrollLeft = 0;
  }, [days]);

  // A stop selected elsewhere: switch tab, then center its minute (instant, clamped).
  useEffect(() => {
    if (!focus) return;
    setDay(focus.sheetIndex);
  }, [focus, setDay]);
  useEffect(() => {
    const region = regionRef.current;
    if (!focus || !region || !fixedWidth || day?.sheet_index !== focus.sheetIndex) return;
    const px = (x(focus.minute) / VIEW_W) * SCROLL_SHEET_WIDTH;
    const max = region.scrollWidth - region.clientWidth;
    region.scrollLeft = Math.min(Math.max(px - region.clientWidth / 2, 0), Math.max(max, 0));
  }, [focus, fixedWidth, day?.sheet_index]);

  const problems = useMemo(() => (day ? sheetProblems(day) : []), [day]);
  useEffect(() => {
    if (problems.length > 0 && import.meta.env.DEV)
      console.error(`Log sheet ${day?.date}: ${problems.join("; ")}`);
  }, [problems, day?.date]);

  if (!day) return <EmptyLogs />;

  const totals = day.totals;
  const summary = `Off ${formatHM(totals.off)} · Sleeper ${formatHM(totals.sleeper)} · Driving ${formatHM(totals.driving)} · On duty ${formatHM(totals.on_duty)} · Total ${formatHM(totals.off + totals.sleeper + totals.driving + totals.on_duty)}`;

  const startPrint = () => {
    printRequested.current = true;
    setPrintAll(true);
  };
  const startPdf = () => {
    setPdf("preparing");
    setPrintAll(true);
  };

  const actions = (
    <>
      <Button onClick={startPrint}>
        <Printer aria-hidden="true" />
        Print logs
      </Button>
      <Button
        variant="secondary"
        onClick={startPdf}
        disabled={pdf === "preparing"}
        className="min-w-40"
      >
        <Download aria-hidden="true" />
        {pdf === "preparing" ? "Preparing PDF..." : "Download PDF"}
      </Button>
    </>
  );

  return (
    <>
      <div ref={measureRef} className="print-hidden">
        <LogSheetTabs days={days} value={day.sheet_index} onValueChange={setDay} actions={actions}>
          <LogSheetTabPanel value={day.sheet_index} className="mt-3 outline-none">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <p id={summaryId} className="font-mono text-sm num">
                {summary}
              </p>
              {scrollMode ? (
                <Button
                  variant="secondary"
                  size="sm"
                  aria-pressed={fit}
                  title="Overview. Use Actual size to read the entries."
                  onClick={() => {
                    setFit((v) => !v);
                  }}
                >
                  {fit ? "Actual size" : "Fit width"}
                </Button>
              ) : null}
            </div>
            {pdf === "error" ? (
              <p role="alert" className="mt-2 text-sm text-danger">
                Could not create the PDF. Use Print logs and choose Save as PDF.
              </p>
            ) : null}
            {scrollMode ? (
              <p className="mt-2 text-sm text-ink-3">
                Scroll sideways to read the full sheet, or print it.
              </p>
            ) : null}

            <div
              ref={regionRef}
              {...(scrollMode && !fit
                ? { role: "region", "aria-label": "Log sheet, scroll horizontally", tabIndex: 0 }
                : {})}
              className={cn(
                "mt-3 rounded-sm",
                scrollMode &&
                  !fit &&
                  "touch-pan-x touch-pan-y touch-pinch-zoom overflow-x-auto overscroll-x-contain",
              )}
            >
              <div
                data-testid="sheet-frame"
                style={
                  fixedWidth
                    ? { width: SCROLL_SHEET_WIDTH }
                    : { width: "100%", maxWidth: SHEET_MAX_WIDTH }
                }
              >
                {problems.length > 0 ? (
                  <LogNotice>
                    This day&apos;s log could not be drawn. Its duty status changes are listed
                    below.
                  </LogNotice>
                ) : (
                  <LogSheet
                    day={day}
                    header={header}
                    sheetCount={sheetCount}
                    timezone={timezone}
                    summaryId={summaryId}
                  />
                )}
              </div>
            </div>
            <LogSheetTable
              day={day}
              header={header}
              timezone={timezone}
              forceOpen={problems.length > 0}
            />
          </LogSheetTabPanel>
        </LogSheetTabs>
      </div>
      {printAll ? (
        <PrintAllLogs
          ref={printRef}
          days={days}
          header={header}
          sheetCount={sheetCount}
          timezone={timezone}
        />
      ) : null}
    </>
  );
}

import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useId } from "react";
import { AssumptionsDialog } from "./AssumptionsDialog";
import { formatDuration, formatHoursPlain, formatMilesWhole, formatSpan } from "./time";
import type { PanelState, TripMeta, TripSummaryData } from "./types";
import { warningCopy } from "./warnings";

/**
 * TripSummary props
 * - state: loading | empty | error | ready. Empty and error render nothing (the empty guidance
 *   and the results alert own those, DESIGN_SYSTEM 9). Ready carries `summary` and `trip`
 *   straight from PlanTripResponse; every figure is printed as the API returned it.
 * - stale: show "Trip inputs changed. Plan trip again to update these results." under the heading.
 */
export type TripSummaryState = PanelState<{ summary: TripSummaryData; trip: TripMeta }>;

export interface TripSummaryProps {
  state: TripSummaryState;
  stale?: boolean;
  className?: string;
}

const FIGURE_COUNT = 5;

export function TripSummary({ state, stale = false, className }: TripSummaryProps) {
  const headingId = useId();
  if (state.status === "empty" || state.status === "error") return null;

  return (
    <section
      aria-labelledby={headingId}
      aria-busy={state.status === "loading"}
      className={cn("rounded-md border border-rule bg-surface p-4 md:p-5", className)}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={headingId} className="label-caps">
          Summary
        </h2>
        {state.status === "ready" ? (
          <AssumptionsDialog assumptions={state.trip.assumptions} />
        ) : null}
      </div>
      {stale && state.status === "ready" ? (
        <p className="mt-2 text-base text-ink-2">
          Trip inputs changed. Plan trip again to update these results.
        </p>
      ) : null}
      {state.status === "loading" ? <SummarySkeleton /> : <SummaryFigures {...state} />}
    </section>
  );
}

function SummarySkeleton() {
  return (
    <div className="mt-3 min-h-24" aria-hidden="true">
      <div className="grid grid-cols-2 gap-x-4 gap-y-4 md:grid-cols-5">
        {Array.from({ length: FIGURE_COUNT }, (_, i) => (
          <div key={i} className="space-y-1">
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
      <Skeleton className="mt-3 h-4 w-64" />
    </div>
  );
}

function SummaryFigures({ summary, trip }: { summary: TripSummaryData; trip: TripMeta }) {
  // Very long trips shrink the figures so nothing truncates (DESIGN_SYSTEM 9).
  const compact = summary.total_distance_mi >= 5000 || summary.sheet_count >= 14;
  const figures: { label: string; value: string }[] = [
    { label: "Distance", value: formatMilesWhole(summary.total_distance_mi) },
    { label: "Driving", value: formatDuration(summary.driving_h) },
    { label: "Trip time", value: formatSpan(summary.trip_duration_h) },
    { label: "Daily logs", value: String(summary.sheet_count) },
    {
      label: "Cycle used at release",
      value: `${formatHoursPlain(summary.cycle_used_end_h)} of 70 h`,
    },
  ];
  return (
    <>
      <div className="mt-3 min-h-24">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-4 md:grid-cols-5">
          {figures.map((f) => (
            <div key={f.label} className="flex min-w-0 flex-col-reverse justify-end">
              <dt className="text-sm text-ink-3">{f.label}</dt>
              <dd
                className={cn(
                  "font-mono font-medium wrap-break-word num",
                  compact ? "text-lg" : "text-lg md:text-xl",
                )}
              >
                {f.value}
              </dd>
            </div>
          ))}
        </dl>
        <StopCountsLine counts={summary.counts} />
      </div>
      {trip.warnings.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {trip.warnings.map((w) => {
            const copy = warningCopy(w);
            return (
              <li key={w.code}>
                <Alert variant="warn" title={copy.title} data-warning-code={w.code}>
                  {copy.body}
                </Alert>
              </li>
            );
          })}
        </ul>
      ) : null}
    </>
  );
}

function StopCountsLine({ counts }: { counts: TripSummaryData["counts"] }) {
  const parts = [
    counts.fuel > 0 ? `${counts.fuel} fuel` : "",
    counts.break > 0 ? `${counts.break} 30-min ${counts.break === 1 ? "break" : "breaks"}` : "",
    counts.rest > 0 ? `${counts.rest} 10-hr ${counts.rest === 1 ? "rest" : "rests"}` : "",
    counts.restart > 0
      ? `${counts.restart} 34-hr ${counts.restart === 1 ? "restart" : "restarts"}`
      : "",
  ].filter(Boolean);
  return (
    <p className="mt-3 text-sm text-ink-3">
      {parts.length > 0
        ? `Stops on the way: ${parts.join(", ")}.`
        : "No fuel, break, rest or restart stops are needed."}
    </p>
  );
}

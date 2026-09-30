import type { ReactNode } from "react";

import { DailyLogs, type DailyLogsState, type LogFocus } from "@/features/logs";
import { LazyMapView, type MapPanelState } from "@/features/map";
import {
  logFocusForStop,
  StopTimeline,
  TripSummary,
  type StopLogFocus,
  type StopTimelineState,
  type TripSummaryState,
} from "@/features/results";
import type { PlanTripResponse } from "@/services/trips";

/**
 * The results workspace: summary, map slot, stop list and daily logs. It lives in its own chunk
 * (loaded by Workspace with React.lazy after the first plan, or prefetched on form focus) so the
 * first paint carries only the shell and the form.
 */

/** Each section's state derived from one plan response. Nothing is stored twice. */
function summaryState(plan: PlanTripResponse | null, loading: boolean): TripSummaryState {
  if (loading) return { status: "loading" };
  if (!plan) return { status: "empty" };
  return { status: "ready", summary: plan.summary, trip: plan.trip };
}

function mapState(plan: PlanTripResponse | null, loading: boolean): MapPanelState {
  if (loading) return { status: "loading" };
  if (!plan) return { status: "empty" };
  return { status: "ready", route: plan.route, stops: plan.stops, timezone: plan.trip.timezone };
}

function stopsState(plan: PlanTripResponse | null, loading: boolean): StopTimelineState {
  if (loading) return { status: "loading" };
  if (!plan) return { status: "empty" };
  return {
    status: "ready",
    stops: plan.stops,
    timeline: plan.timeline,
    days: plan.days,
    timezone: plan.trip.timezone,
    counts: plan.summary.counts,
  };
}

function logsState(plan: PlanTripResponse | null, loading: boolean): DailyLogsState {
  if (loading) return { status: "loading" };
  if (!plan) return { status: "empty" };
  return {
    status: "ready",
    days: plan.days,
    header: plan.trip.log_header,
    sheetCount: plan.summary.sheet_count,
    timezone: plan.trip.timezone,
  };
}

export interface ResultsMainProps {
  plan: PlanTripResponse | null;
  loading: boolean;
  /** Replaces the summary card (the waking-server card). */
  summarySlot?: ReactNode;
  stale: boolean;
  selectedStopId: string | null;
  onSelectStop: (stopId: string | null) => void;
  /** The moment on a log sheet that the selected stop starts (for DailyLogs `focus`). */
  onLogFocus: (focus: StopLogFocus) => void;
}

export function ResultsMain({
  plan,
  loading,
  summarySlot,
  stale,
  selectedStopId,
  onSelectStop,
  onLogFocus,
}: ResultsMainProps) {
  function select(id: string | null) {
    onSelectStop(id);
    const stop = plan?.stops.find((candidate) => candidate.id === id);
    if (plan && stop) {
      const focus = logFocusForStop(stop, plan.days, plan.trip.timezone);
      if (focus) onLogFocus(focus);
    }
  }

  return (
    <>
      {summarySlot ?? <TripSummary state={summaryState(plan, loading)} stale={stale} />}
      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <LazyMapView
          state={mapState(plan, loading)}
          selectedStopId={selectedStopId}
          onSelectStop={select}
        />
        <StopTimeline
          state={stopsState(plan, loading)}
          selectedStopId={selectedStopId}
          onSelectStop={select}
        />
      </div>
    </>
  );
}

export interface ResultsLogsProps {
  plan: PlanTripResponse | null;
  loading: boolean;
  focus: LogFocus | undefined;
}

export function ResultsLogs({ plan, loading, focus }: ResultsLogsProps) {
  return <DailyLogs state={logsState(plan, loading)} focus={focus} />;
}

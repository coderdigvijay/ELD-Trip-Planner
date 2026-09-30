import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { LogFocus } from "@/features/logs";
import { LogSheetSkeleton } from "@/features/logs/LogSheetStates";
import { EmptyLogs, LogsSection } from "@/features/logs/LogsSection";
import { prefetchMapView } from "@/features/map";
import { MapSkeleton } from "@/features/map/MapSkeleton";
import {
  EmptyGuidance,
  locationLabel,
  PlanAlert,
  TripForm,
  toPlanRequest,
  useServerHealth,
  usePlanTrip,
  useTripForm,
  WakingSummary,
  writeShare,
  type PlanFailure,
  type TripFormValues,
} from "@/features/trip-form";
import { useMediaQuery } from "@/lib/useMediaQuery";

const PHONE = "(max-width: 47.99rem)";
const APP_TITLE = "ELD Trip Planner";

// The results chunk (summary, stops, map slot, logs) loads after the first plan, or on form focus.
const loadResults = () => import("./ResultsWorkspace");
const ResultsMain = lazy(() => loadResults().then((m) => ({ default: m.ResultsMain })));
const ResultsLogs = lazy(() => loadResults().then((m) => ({ default: m.ResultsLogs })));

function prefetchResults(): void {
  void loadResults();
  void prefetchMapView();
}

/** Reserved-height stand-in while the results chunk downloads (same footprint as the sections). */
function ResultsFallback() {
  return (
    <>
      <section
        aria-busy="true"
        className="min-h-40 rounded-md border border-rule bg-surface p-4 md:p-5"
      >
        <h2 className="label-caps">Summary</h2>
        <div role="status" className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-5">
          <span className="sr-only">Loading results</span>
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </section>
      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <MapSkeleton />
        <Skeleton className="h-64 w-full lg:h-120 xl:h-100" />
      </div>
    </>
  );
}

/** True while the form differs from the inputs of the plan on screen (DESIGN_SYSTEM 4.4). */
function useInputsChanged(
  api: ReturnType<typeof useTripForm>,
  submitted: TripFormValues | null,
): boolean {
  const [changed, setChanged] = useState(false);
  const { form } = api;
  useEffect(() => {
    if (!submitted) return;
    const baseline = JSON.stringify(submitted);
    return form.subscribe({
      formState: { values: true },
      callback: ({ values }) => {
        setChanged(JSON.stringify(values) !== baseline);
      },
    });
  }, [form, submitted]);
  return submitted !== null && changed;
}

export function Workspace() {
  const api = useTripForm();
  const { focusField, applyProblems, fillExample } = api;
  const health = useServerHealth();
  const isPhone = useMediaQuery(PHONE);
  const [collapsed, setCollapsed] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [submitted, setSubmitted] = useState<TripFormValues | null>(null);
  const [lastClick, setLastClick] = useState<TripFormValues | null>(null);
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const [logFocus, setLogFocus] = useState<LogFocus | undefined>(undefined);
  const submitRef = useRef<HTMLButtonElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const pendingValues = useRef<TripFormValues | null>(null);

  const planner = usePlanTrip({
    onFailure: (failure: PlanFailure) => {
      if (failure.kind === "fields") {
        flushSync(() => {
          setCollapsed(false);
        });
        applyProblems(failure.problems);
      }
    },
    onSuccess: (plan) => {
      if (pendingValues.current) {
        writeShare(pendingValues.current);
        setSubmitted(pendingValues.current);
      }
      const { places } = plan.trip;
      document.title = `${places.current.label} to ${places.dropoff.label} . ${APP_TITLE}`;
      const logs = plan.summary.sheet_count;
      setAnnouncement(`Trip planned. ${String(logs)} daily ${logs === 1 ? "log" : "logs"}.`);
      if (isPhone) {
        requestAnimationFrame(() => {
          const heading = resultsRef.current?.querySelector("h2");
          if (heading instanceof HTMLElement) {
            heading.tabIndex = -1;
            heading.focus();
          }
        });
      }
    },
  });

  const stale = useInputsChanged(api, submitted);
  const waking = planner.isPending && health.isPending;
  const plan = planner.isPending ? null : planner.plan;

  function handleSubmit(values: TripFormValues) {
    pendingValues.current = values;
    setLastClick(values);
    setAnnouncement("");
    setSelectedStopId(null);
    setLogFocus(undefined);
    if (isPhone) setCollapsed(true);
    planner.submit(toPlanRequest(values));
  }

  function editTrip(field: Parameters<typeof focusField>[0] = "current_location") {
    flushSync(() => {
      setCollapsed(false);
    });
    focusField(field);
  }

  // The trip card shows the inputs of the last click.
  const tripLine = lastClick
    ? [lastClick.current_location, lastClick.pickup_location, lastClick.dropoff_location]
        .map(locationLabel)
        .join(" to ")
    : "";

  const alert = planner.failure?.kind === "alert" ? planner.failure : null;
  const showEmpty = !planner.isPending && !plan && !planner.lastPlan;

  return (
    <div className="grid gap-6 lg:grid-cols-[344px_1fr] lg:gap-8 xl:grid-cols-[360px_1fr]">
      <section
        aria-labelledby="trip-heading"
        className="self-start rounded-md border border-rule bg-card p-4 md:p-5"
      >
        <h2 id="trip-heading" className="label-caps">
          Trip
        </h2>
        {collapsed ? (
          <div className="mt-3 flex flex-col items-start gap-3 md:hidden">
            <p className="text-lg text-foreground">{tripLine}</p>
            <p className="font-mono text-base text-ink-2 num">
              {lastClick?.current_cycle_used_hours ?? 0} h used
            </p>
            <p role="status" className="text-base text-ink-2">
              {planner.isPending ? "Planning route..." : ""}
            </p>
            <Button
              variant="secondary"
              onClick={() => {
                editTrip();
              }}
            >
              Edit trip
            </Button>
          </div>
        ) : null}
        <div className={collapsed ? "mt-4 max-md:hidden" : "mt-4"}>
          <TripForm
            api={api}
            pending={planner.isPending}
            onSubmit={handleSubmit}
            submitRef={submitRef}
            onFocusWithin={() => {
              prefetchResults();
            }}
          />
        </div>
      </section>

      <div ref={resultsRef} className="flex min-w-0 flex-col gap-6">
        <p role="status" className="sr-only">
          {announcement}
        </p>
        {alert && !planner.isPending ? (
          <PlanAlert
            failure={alert}
            failedAtS={planner.failedAtS}
            showingPrevious={planner.lastPlan !== null}
            onRetry={() => {
              if (pendingValues.current) planner.submit(toPlanRequest(pendingValues.current));
            }}
            onEdit={editTrip}
          />
        ) : null}
        {showEmpty ? (
          <EmptyGuidance
            onFillExample={() => {
              fillExample();
              submitRef.current?.focus();
            }}
          />
        ) : null}
        {!showEmpty ? (
          <Suspense fallback={<ResultsFallback />}>
            <ResultsMain
              plan={plan}
              loading={planner.isPending}
              summarySlot={
                waking ? (
                  <WakingSummary
                    startedAtS={planner.submittedAtS ?? 0}
                    onCancel={() => {
                      planner.cancel();
                      setCollapsed(false);
                    }}
                  />
                ) : undefined
              }
              stale={stale}
              selectedStopId={selectedStopId}
              onSelectStop={setSelectedStopId}
              onLogFocus={(focus) => {
                setLogFocus((previous) => ({ ...focus, nonce: (previous?.nonce ?? 0) + 1 }));
              }}
            />
          </Suspense>
        ) : null}
      </div>

      <div className="min-w-0 lg:col-span-2">
        {showEmpty ? (
          <LogsSection>
            <EmptyLogs />
          </LogsSection>
        ) : (
          <Suspense
            fallback={
              <LogsSection>
                <LogSheetSkeleton />
              </LogsSection>
            }
          >
            <ResultsLogs plan={plan} loading={planner.isPending} focus={logFocus} />
          </Suspense>
        )}
      </div>
    </div>
  );
}

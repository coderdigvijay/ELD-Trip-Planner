import { useEffect, useId, useRef, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { StopGlyph } from "./StopGlyph";
import { KIND_LABEL, STATUS_CODE, STATUS_NAME } from "./stopKinds";
import { buildDayGroups, type TimelineRow } from "./timelineModel";
import type { SelectionProps } from "./selection";
import { formatDuration, formatMilesWhole, zoneLabel } from "./time";
import type {
  LogDayRef,
  PanelState,
  Stop,
  TimelineEvent,
  TripSummaryData,
  TripTimezone,
} from "./types";

/**
 * StopTimeline props
 * - state: loading | empty | error | ready. Empty and error render nothing (the empty guidance
 *   and the results alert own those). Ready takes `stops`, `timeline`, `days` (LogDay[] works),
 *   `timezone` (trip.timezone) and `counts` (summary.counts) straight from PlanTripResponse.
 * - Selection (shared with MapView, see SelectionProps): selectedStopId, onSelectStop(id | null),
 *   optional onSelectDay(sheetIndex), optional hoveredStopId / onHoverStop.
 *   Click or Enter on a row selects it; Escape clears; the selected row scrolls into view inside
 *   this panel only (the page never scrolls).
 * - className: the App sets the panel height at lg+ (for example `lg:h-90`); the list scrolls inside it.
 */
export type StopTimelineState = PanelState<{
  stops: readonly Stop[];
  timeline: readonly TimelineEvent[];
  days: readonly LogDayRef[];
  timezone: TripTimezone;
  counts: TripSummaryData["counts"];
}>;

export interface StopTimelineProps extends Partial<SelectionProps> {
  state: StopTimelineState;
  className?: string;
}

const SKELETON_ROWS = 8;

export function StopTimeline({ state, className, ...selection }: StopTimelineProps) {
  const headingId = useId();
  if (state.status === "empty" || state.status === "error") return null;

  return (
    <section
      aria-labelledby={headingId}
      aria-busy={state.status === "loading"}
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-md border border-rule bg-surface p-4 md:p-5",
        className,
      )}
    >
      <h2 id={headingId} className="label-caps">
        Stops
      </h2>
      {state.status === "loading" ? (
        <TimelineSkeleton />
      ) : (
        <ReadyTimeline {...state} {...selection} />
      )}
    </section>
  );
}

function TimelineSkeleton() {
  return (
    <div className="mt-3 space-y-3" aria-hidden="true">
      {Array.from({ length: SKELETON_ROWS }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}

type ReadyProps = Extract<StopTimelineState, { status: "ready" }> & Partial<SelectionProps>;

function ReadyTimeline({
  stops,
  timeline,
  days,
  timezone,
  counts,
  selectedStopId = null,
  onSelectStop,
  onSelectDay,
  hoveredStopId = null,
  onHoverStop,
}: ReadyProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const groups = buildDayGroups(stops, timeline, timezone, days);
  const noExtraStops = counts.fuel + counts.break + counts.rest + counts.restart === 0;

  // Keep the selected row visible by moving only this panel's scroll, never the page (DESIGN_SYSTEM 6.5).
  useEffect(() => {
    const scroller = scrollerRef.current;
    if (!scroller || !selectedStopId) return;
    const row = [...scroller.querySelectorAll<HTMLElement>("[data-stop-id]")].find(
      (el) => el.dataset.stopId === selectedStopId,
    );
    if (!row) return;
    const above = row.offsetTop - scroller.scrollTop;
    const below = above + row.offsetHeight - scroller.clientHeight;
    if (above < 0) scroller.scrollTop += above;
    else if (below > 0) scroller.scrollTop += below;
  }, [selectedStopId]);

  const select = (stop: Stop, sheetIndex: number | undefined) => {
    onSelectStop?.(stop.id);
    if (sheetIndex !== undefined) onSelectDay?.(sheetIndex);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape" && selectedStopId) {
      event.stopPropagation();
      onSelectStop?.(null);
    }
  };

  return (
    // The keydown handler only listens for Escape bubbling up from the row buttons inside.
    <div className="mt-1 flex min-h-0 flex-1 flex-col" onKeyDown={onKeyDown}>
      <p className="text-sm text-ink-3">{zoneLabel(timezone)}</p>
      {noExtraStops ? (
        <p className="mt-2 text-base text-ink-2">No stops needed. The trip fits in one shift.</p>
      ) : null}
      <div ref={scrollerRef} className="relative mt-3 min-h-0 flex-1 lg:overflow-y-auto">
        {groups.map((group) => (
          <div key={group.key} className="mb-4 last:mb-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 border-b border-rule pb-1">
              <h3 className="text-base font-semibold">
                Day {group.dayNumber}{" "}
                <span className="font-normal text-ink-2 num">{group.label}</span>
              </h3>
              {onSelectDay && group.sheetIndex !== undefined ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    onSelectDay(group.sheetIndex ?? 1);
                  }}
                  aria-label={`View log for day ${group.dayNumber}`}
                >
                  View log
                </Button>
              ) : null}
            </div>
            <ol className="m-0 list-none p-0">
              {group.rows.map((row) => (
                <StopRow
                  key={row.key}
                  row={row}
                  selected={row.stop.id === selectedStopId}
                  hovered={row.stop.id === hoveredStopId}
                  onSelect={() => {
                    select(row.stop, group.sheetIndex);
                  }}
                  onHover={onHoverStop}
                />
              ))}
            </ol>
          </div>
        ))}
      </div>
    </div>
  );
}

interface StopRowProps {
  row: TimelineRow;
  selected: boolean;
  hovered: boolean;
  onSelect: () => void;
  onHover?: (stopId: string | null) => void;
}

function StopRow({ row, selected, hovered, onSelect, onHover }: StopRowProps) {
  const { stop } = row;
  const kindLabel = KIND_LABEL[stop.kind];
  const detail = stop.reason !== "" ? stop.reason : stop.note;
  const fullName = `${kindLabel}${row.cont ? " (cont.)" : ""}, ${stop.label}`;
  // Spelled out for assistive tech: the visible spans carry no whitespace between them.
  const accessibleName = [
    `${row.time}, ${fullName}`,
    detail,
    row.durationH > 0
      ? `${STATUS_NAME[stop.duty_status]}, ${formatDuration(row.durationH)}`
      : STATUS_NAME[stop.duty_status],
  ]
    .filter((part) => part !== "")
    .join(". ");

  return (
    <>
      {row.drive ? (
        <li className="ms-13 border-s border-dotted border-rule-strong py-1 ps-3 text-sm text-ink-3">
          <span className="num">
            Drive {formatDuration(row.drive.hours)} . {formatMilesWhole(row.drive.miles)}
          </span>
        </li>
      ) : null}
      <li data-stop-id={stop.id} data-cont={row.cont || undefined}>
        <button
          type="button"
          aria-pressed={selected}
          title={fullName}
          aria-label={accessibleName}
          onClick={onSelect}
          onMouseEnter={() => {
            onHover?.(stop.id);
          }}
          onMouseLeave={() => {
            onHover?.(null);
          }}
          className={cn(
            "grid w-full cursor-pointer grid-cols-[3rem_1.5rem_minmax(0,1fr)_auto] items-start gap-x-2 border-s-2 border-transparent px-1 py-2 text-start text-base hover:bg-surface-sunk focus-visible:outline-2 focus-visible:outline-offset-[-2px]",
            hovered && "bg-surface-sunk",
            selected && "border-pen bg-pen-tint hover:bg-pen-tint",
          )}
        >
          <span className="pt-px font-mono text-sm num">{row.time}</span>
          <StopGlyph kind={stop.kind} size={20} className="mt-px" />
          <span className="min-w-0">
            <span className="line-clamp-2 font-medium wrap-break-word">
              {kindLabel}
              {row.cont ? " (cont.)" : ""}
              <span className="font-normal text-ink-2"> . {stop.label}</span>
            </span>
            {detail !== "" ? (
              <span className="line-clamp-2 block text-sm wrap-break-word text-ink-2">
                {detail}
              </span>
            ) : null}
          </span>
          <span className="flex items-baseline gap-2 text-sm">
            <span
              className="rounded-sm border border-rule-strong px-1 font-mono text-xs"
              title={STATUS_NAME[stop.duty_status]}
            >
              <span aria-hidden="true">{STATUS_CODE[stop.duty_status]}</span>
              <span className="sr-only">{STATUS_NAME[stop.duty_status]}</span>
            </span>
            {row.durationH > 0 ? (
              <span className="min-w-12 text-end text-ink-2 num">
                {formatDuration(row.durationH)}
              </span>
            ) : null}
          </span>
        </button>
      </li>
    </>
  );
}

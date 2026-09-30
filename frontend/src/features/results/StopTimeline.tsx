import { TriangleAlert } from "lucide-react";
import { useEffect, useRef, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/lib/useMediaQuery";
import { useIsHovered, type HoverStore } from "./hoverStore";
import { StopGlyph } from "./StopGlyph";
import { StopsFrame, StopsSkeletonRows } from "./StopsFrame";
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
 * - className: extra classes for the card. From lg the card has a fixed height (DESIGN_SYSTEM 3.6) and
 *   the list scrolls inside it as a labelled, focusable region, so every row stays reachable.
 */
export type StopTimelineState = PanelState<{
  stops: readonly Stop[];
  timeline: readonly TimelineEvent[];
  days: readonly LogDayRef[];
  timezone: TripTimezone;
  counts: TripSummaryData["counts"];
  /** `LABELS_APPROXIMATED` is in trip.warnings: say so under the heading. */
  approximate?: boolean;
}>;

export interface StopTimelineProps extends Partial<SelectionProps> {
  state: StopTimelineState;
  className?: string;
}

const BOUNDED_PANEL = "(min-width: 64rem)";

export function StopTimeline({ state, className, ...selection }: StopTimelineProps) {
  if (state.status === "empty" || state.status === "error") return null;

  return (
    <StopsFrame busy={state.status === "loading"} className={className}>
      {state.status === "loading" ? (
        <StopsSkeletonRows />
      ) : (
        <ReadyTimeline {...state} {...selection} />
      )}
    </StopsFrame>
  );
}

type ReadyProps = Extract<StopTimelineState, { status: "ready" }> & Partial<SelectionProps>;

function ReadyTimeline({
  stops,
  timeline,
  days,
  timezone,
  counts,
  approximate = false,
  selectedStopId = null,
  onSelectStop,
  onSelectDay,
  hover,
}: ReadyProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  // Only a bounded panel scrolls; below lg the list flows in the page and needs no extra tab stop.
  const bounded = useMediaQuery(BOUNDED_PANEL);
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
    <div
      className="mt-1 flex min-h-0 flex-1 animate-reveal flex-col [animation-delay:40ms] motion-reduce:animate-none"
      onKeyDown={onKeyDown}
    >
      {approximate ? (
        <p role="status" className="mb-1 flex items-start gap-2 text-sm text-warn">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          Some stop locations are approximate.
        </p>
      ) : null}
      <p className="text-sm text-ink-3">{zoneLabel(timezone)}</p>
      {noExtraStops ? (
        <p className="mt-2 text-base text-ink-2">No stops needed. The trip fits in one shift.</p>
      ) : null}
      <div
        ref={scrollerRef}
        {...(bounded ? { role: "region", tabIndex: 0, "aria-label": "Trip timeline" } : {})}
        className="relative mt-3 min-h-0 flex-1 [scrollbar-width:thin] [scrollbar-color:var(--color-ink-3)_transparent] lg:overflow-y-auto lg:pe-2 lg:focus-visible:outline-offset-[-2px]"
      >
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
                  onSelect={() => {
                    select(row.stop, group.sheetIndex);
                  }}
                  hover={hover}
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
  hover: HoverStore | undefined;
  onSelect: () => void;
}

function StopRow({ row, selected, hover, onSelect }: StopRowProps) {
  const { stop } = row;
  const hovered = useIsHovered(hover, [stop.id]);
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
          aria-label={accessibleName}
          onClick={onSelect}
          onMouseEnter={() => {
            hover?.set(stop.id);
          }}
          onMouseLeave={() => {
            hover?.set(null);
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
            <span className="rounded-sm border border-rule-strong px-1 font-mono text-xs">
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

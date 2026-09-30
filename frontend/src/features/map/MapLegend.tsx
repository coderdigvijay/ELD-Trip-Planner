import { StopGlyph } from "../results/StopGlyph";
import { KIND_LABEL, LEGEND_KINDS } from "../results/stopKinds";
import type { Route, Stop } from "../results/types";

interface MapLegendProps {
  stops: readonly Stop[];
  route: Route;
}

function LegLine({ dashed }: { dashed: boolean }) {
  return (
    <svg aria-hidden="true" focusable="false" width="24" height="16" viewBox="0 0 24 16">
      <line
        x1="1"
        y1="8"
        x2="23"
        y2="8"
        strokeWidth="4"
        strokeDasharray={dashed ? "6 4" : undefined}
        className="stroke-pen"
      />
    </svg>
  );
}

/** A real list under the map: only the stop types present, plus the leg patterns that are drawn. */
export function MapLegend({ stops, route }: MapLegendProps) {
  const present = LEGEND_KINDS.filter((kind) => stops.some((s) => s.kind === kind));
  const drawn = (index: number) => route.legs.some((l) => l.index === index && l.polyline !== "");
  return (
    <ul
      aria-label="Map legend"
      className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-ink-2"
    >
      {present.map((kind) => (
        <li key={kind} className="flex items-center gap-1.5">
          <StopGlyph kind={kind} size={16} />
          {KIND_LABEL[kind]}
        </li>
      ))}
      {drawn(0) ? (
        <li className="flex items-center gap-1.5">
          <LegLine dashed />
          To pickup
        </li>
      ) : null}
      {drawn(1) ? (
        <li className="flex items-center gap-1.5">
          <LegLine dashed={false} />
          To dropoff
        </li>
      ) : null}
    </ul>
  );
}

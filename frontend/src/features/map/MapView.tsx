import polyline from "@mapbox/polyline";
import {
  divIcon,
  type LatLngBoundsExpression,
  type LatLngTuple,
  type Map as LeafletMap,
  type Marker as LeafletMarker,
} from "leaflet";
import "leaflet/dist/leaflet.css";
import { TriangleAlert } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type RefObject,
} from "react";
import {
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";

import { Button } from "@/components/ui/button";
import { KIND_LABEL } from "../results/stopKinds";
import type { SelectionProps } from "../results/selection";
import { formatClock } from "../results/time";
import type { Route, Stop, StopKind, TripTimezone } from "../results/types";
import { stopGlyphSvg } from "./glyphSvg";
import { MapLegend } from "./MapLegend";
import { groupIdOf, groupStops, type MarkerGroup } from "./markerGroups";
import { RoutePanel } from "./RoutePanel";
import { MAX_ZOOM, OSM_SOURCE, tileSources, type TileSource } from "./tiles";
import "./map.css";

/**
 * MapView props (this module is the lazy chunk; import it through LazyMapView)
 * - route, stops, timezone: `route`, `stops`, `trip.timezone` from PlanTripResponse, unchanged.
 * - selectedStopId / onSelectStop / onSelectDay / hoveredStopId / onHoverStop: the shared
 *   SelectionProps contract (DESIGN_SYSTEM 6.5). A marker click calls onSelectStop(primaryStopId)
 *   and onSelectDay(sheetIndex is NOT known here, so the App derives it with logFocusForStop).
 * - Esc clears the selection. Keyboard: Tab to a marker, Enter or Space selects it.
 */
export interface MapViewProps extends Partial<
  Pick<SelectionProps, "selectedStopId" | "onSelectStop" | "hoveredStopId" | "onHoverStop">
> {
  route: Route;
  stops: readonly Stop[];
  timezone: TripTimezone;
  className?: string;
}

const FIT_OPTIONS = { padding: [32, 32] as [number, number], maxZoom: 12, animate: false };
const MIN_SELECT_ZOOM = 7;
/** Tiles that fail before the first one loads: enough to say the source is down, not one bad tile. */
const TILE_FAILURE_THRESHOLD = 3;

const prefersReducedMotion = (): boolean =>
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function boundsOf(route: Route): LatLngBoundsExpression {
  const b = route.bounds;
  return [
    [b.south, b.west],
    [b.north, b.east],
  ];
}

function markerIcon(kind: StopKind, extra: number) {
  const { html, size } = stopGlyphSvg(kind);
  // `html` is built from constants in glyphSpec and `extra` is a number: no API string is ever injected.
  const badge = extra > 0 ? `<span class="stop-marker__badge">+${extra}</span>` : "";
  return divIcon({
    html: `<span class="stop-marker__body">${html}</span>${badge}`,
    className: "stop-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

export default function MapView({
  route,
  stops,
  timezone,
  selectedStopId = null,
  onSelectStop,
  hoveredStopId = null,
  onHoverStop,
  className,
}: MapViewProps) {
  const [map, setMap] = useState<LeafletMap | null>(null);
  const groups = useMemo(() => groupStops(stops), [stops]);
  const selectedGroupId = groupIdOf(groups, selectedStopId);
  const hoveredGroupId = groupIdOf(groups, hoveredStopId);
  const legs = useMemo(
    () =>
      route.legs.map((leg) => ({
        index: leg.index,
        positions: polyline.decode(leg.polyline),
      })),
    [route.legs],
  );
  // A marker click came from the map, which is already showing it: do not pan.
  const pickedOnMapRef = useRef(false);

  const pick = useCallback(
    (group: MarkerGroup) => {
      if (group.id !== selectedGroupId) pickedOnMapRef.current = true;
      onSelectStop?.(group.id);
    },
    [onSelectStop, selectedGroupId],
  );

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape" && selectedStopId) onSelectStop?.(null);
  };

  const { source, tileFailed, handlers } = useTileFallback();

  return (
    <RoutePanel
      className={className}
      onKeyDown={onKeyDown}
      action={
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            map?.fitBounds(boundsOf(route), FIT_OPTIONS);
          }}
        >
          Fit route
        </Button>
      }
      footer={
        <div className="space-y-2">
          <MapLegend stops={stops} route={route} />
          {tileFailed ? (
            <p role="status" className="flex items-center gap-2 text-sm text-warn">
              <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
              Map tiles did not load. The route and stops are still shown.
            </p>
          ) : null}
        </div>
      }
    >
      <MapContainer
        ref={setMap}
        bounds={boundsOf(route)}
        boundsOptions={FIT_OPTIONS}
        maxZoom={MAX_ZOOM}
        scrollWheelZoom={false}
        className="size-full"
      >
        <TileLayer
          key={source.id}
          url={source.url}
          attribution={source.attribution}
          subdomains={source.subdomains}
          maxZoom={MAX_ZOOM}
          eventHandlers={handlers}
        />
        {legs.map((leg) =>
          leg.positions.length > 1 ? (
            <RouteLeg key={leg.index} positions={leg.positions} dashed={leg.index === 0} />
          ) : null,
        )}
        {groups.map((group) => (
          <StopMarker
            key={group.id}
            group={group}
            timezone={timezone}
            selected={group.id === selectedGroupId}
            hovered={group.id === hoveredGroupId}
            onPick={pick}
            onHover={onHoverStop}
          />
        ))}
        <MapBehavior
          route={route}
          groups={groups}
          selectedGroupId={selectedGroupId}
          pickedOnMapRef={pickedOnMapRef}
        />
      </MapContainer>
    </RoutePanel>
  );
}

/** Try the first source, fall back to the next (OSM) when it loads no tile, then give up and say so (DESIGN_SYSTEM 6.6). */
function useTileFallback() {
  const sources = useMemo<TileSource[]>(() => tileSources(import.meta.env.VITE_CARTO_API_KEY), []);
  const [index, setIndex] = useState(0);
  const [tileFailed, setTileFailed] = useState(false);
  const counts = useRef({ loaded: 0, errors: 0 });

  const handlers = useMemo(
    () => ({
      tileload: () => {
        counts.current.loaded += 1;
        setTileFailed(false);
      },
      tileerror: () => {
        counts.current.errors += 1;
        if (counts.current.loaded > 0 || counts.current.errors < TILE_FAILURE_THRESHOLD) return;
        counts.current = { loaded: 0, errors: 0 };
        setIndex((current) => {
          if (current + 1 < sources.length) return current + 1;
          setTileFailed(true);
          return current;
        });
      },
    }),
    [sources],
  );
  return { source: sources[index] ?? OSM_SOURCE, tileFailed, handlers };
}

function RouteLeg({ positions, dashed }: { positions: LatLngTuple[]; dashed: boolean }) {
  // Pattern, not color, separates the legs. Dashes use butt caps so the gaps stay visible.
  const shared = {
    lineCap: dashed ? ("butt" as const) : ("round" as const),
    lineJoin: "round" as const,
    opacity: 1,
    interactive: false,
    dashArray: dashed ? "8 6" : undefined,
  };
  return (
    <>
      <Polyline
        positions={positions}
        pathOptions={{ ...shared, className: "route-casing", weight: 7 }}
      />
      <Polyline
        positions={positions}
        pathOptions={{ ...shared, className: "route-line", weight: 4 }}
      />
    </>
  );
}

interface StopMarkerProps {
  group: MarkerGroup;
  timezone: TripTimezone;
  selected: boolean;
  hovered: boolean;
  onPick: (group: MarkerGroup) => void;
  onHover?: (stopId: string | null) => void;
}

function StopMarker({ group, timezone, selected, hovered, onPick, onHover }: StopMarkerProps) {
  const markerRef = useRef<LeafletMarker>(null);
  const extra = group.stops.length - 1;
  const icon = useMemo(() => markerIcon(group.primary.kind, extra), [group.primary.kind, extra]);
  const name = group.stops
    .map((s) => `${KIND_LABEL[s.kind]}, ${s.label}, ${formatClock(s.arrive_at, timezone)}`)
    .join("; ");

  const eventHandlers = useMemo(
    () => ({
      click: () => {
        onPick(group);
      },
      mouseover: () => onHover?.(group.id),
      mouseout: () => onHover?.(null),
    }),
    [group, onPick, onHover],
  );

  // Name, pressed state and the selected/hover classes go on Leaflet's own icon element, so focus never moves.
  useEffect(() => {
    const el = markerRef.current?.getElement();
    if (!el) return;
    el.setAttribute("aria-label", name);
    el.setAttribute("aria-pressed", String(selected));
    el.classList.toggle("is-selected", selected);
    el.classList.toggle("is-hover", hovered);
  }, [icon, name, selected, hovered]);

  // Tooltip follows selection and keyboard focus; Space activates like Enter (Leaflet only handles Enter).
  useEffect(() => {
    const marker = markerRef.current;
    const el = marker?.getElement();
    if (!marker || !el) return;
    const open = () => {
      marker.openTooltip();
    };
    const close = () => {
      if (!el.classList.contains("is-selected")) marker.closeTooltip();
    };
    const onSpace = (event: globalThis.KeyboardEvent) => {
      if (event.key !== " ") return;
      event.preventDefault();
      marker.fire("click");
    };
    el.addEventListener("focus", open);
    el.addEventListener("blur", close);
    el.addEventListener("keydown", onSpace);
    return () => {
      el.removeEventListener("focus", open);
      el.removeEventListener("blur", close);
      el.removeEventListener("keydown", onSpace);
    };
  }, [icon]);

  useEffect(() => {
    const marker = markerRef.current;
    if (!marker) return;
    if (selected) marker.openTooltip();
    else marker.closeTooltip();
  }, [selected]);

  return (
    <Marker
      ref={markerRef}
      position={[group.primary.lat, group.primary.lng]}
      icon={icon}
      keyboard
      riseOnHover
      zIndexOffset={selected ? 1000 : 0}
      eventHandlers={eventHandlers}
    >
      <Tooltip direction="top" offset={[0, -14]} className="stop-tooltip">
        <ul className="m-0 list-none space-y-1 p-0">
          {group.stops.map((s) => (
            <li key={s.id}>
              <span className="font-semibold">{KIND_LABEL[s.kind]}</span> . {s.label}
              <span className="block font-mono text-xs num">
                {formatClock(s.arrive_at, timezone)}
              </span>
              {s.reason !== "" ? <span className="block text-xs">{s.reason}</span> : null}
            </li>
          ))}
        </ul>
      </Tooltip>
    </Marker>
  );
}

interface MapBehaviorProps {
  route: Route;
  groups: readonly MarkerGroup[];
  selectedGroupId: string | null;
  pickedOnMapRef: RefObject<boolean>;
}

/** Everything that talks to the Leaflet map instance: labels, wheel gate, resize, refit, pan to selection. */
function MapBehavior({ route, groups, selectedGroupId, pickedOnMapRef }: MapBehaviorProps) {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    map.attributionControl.setPrefix(false);
    container.setAttribute("role", "region");
    container.setAttribute(
      "aria-label",
      "Route map. Arrow keys pan, plus and minus zoom. Stops are listed below the map.",
    );
  }, [map]);

  // No scroll trap: the wheel zooms only after the map is clicked or focused.
  useMapEvents({
    click: () => {
      map.scrollWheelZoom.enable();
    },
  });
  useEffect(() => {
    const container = map.getContainer();
    const enable = () => map.scrollWheelZoom.enable();
    const disable = () => map.scrollWheelZoom.disable();
    container.addEventListener("focus", enable);
    container.addEventListener("blur", disable);
    return () => {
      container.removeEventListener("focus", enable);
      container.removeEventListener("blur", disable);
    };
  }, [map]);

  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => {
      observer.disconnect();
    };
  }, [map]);

  const { south, west, north, east } = route.bounds;
  useEffect(() => {
    map.fitBounds(
      [
        [south, west],
        [north, east],
      ],
      FIT_OPTIONS,
    );
  }, [map, south, west, north, east]);

  useEffect(() => {
    if (!selectedGroupId) return;
    if (pickedOnMapRef.current) {
      pickedOnMapRef.current = false;
      return;
    }
    const group = groups.find((g) => g.id === selectedGroupId);
    if (!group) return;
    const target: LatLngTuple = [group.primary.lat, group.primary.lng];
    const zoom = Math.max(map.getZoom(), MIN_SELECT_ZOOM);
    if (prefersReducedMotion()) map.setView(target, zoom, { animate: false });
    else map.flyTo(target, zoom, { duration: 0.24 });
  }, [map, groups, selectedGroupId, pickedOnMapRef]);

  return null;
}

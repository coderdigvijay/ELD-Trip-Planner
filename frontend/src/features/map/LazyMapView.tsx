import { lazy, Suspense } from "react";
import { ErrorBoundary } from "react-error-boundary";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { MapViewProps } from "./MapView";
import { MapSkeleton } from "./MapSkeleton";
import type { PanelState } from "../results/types";

/** Start downloading the map chunk early (call it when the form gains focus). */
export const prefetchMapView = () => import("./MapView");

const MapView = lazy(prefetchMapView);

/**
 * LazyMapView props
 * - state: loading | empty | error | ready. Loading shows the fixed-height skeleton without loading
 *   the chunk; empty and error render nothing (guidance and the results alert own those). Ready
 *   carries the MapView props (route, stops, timezone) from PlanTripResponse.
 * - Selection props are the shared SelectionProps contract, see MapView.
 * - A failed chunk shows an inline map error; the stop list and the logs still work.
 */
export type MapPanelState = PanelState<Pick<MapViewProps, "route" | "stops" | "timezone">>;

export interface LazyMapViewProps extends Partial<
  Pick<
    MapViewProps,
    "selectedStopId" | "onSelectStop" | "hoveredStopId" | "onHoverStop" | "className"
  >
> {
  state: MapPanelState;
}

export function LazyMapView({ state, ...rest }: LazyMapViewProps) {
  if (state.status === "empty" || state.status === "error") return null;
  if (state.status === "loading") return <MapSkeleton className={rest.className} />;
  const { route, stops, timezone } = state;
  return (
    <ErrorBoundary
      resetKeys={[route]}
      fallbackRender={({ resetErrorBoundary }) => (
        <Alert
          variant="danger"
          title="The map could not load"
          action={
            <Button variant="secondary" size="sm" onClick={resetErrorBoundary}>
              Try again
            </Button>
          }
        >
          Every stop is still listed below, and the daily logs are not affected.
        </Alert>
      )}
    >
      <Suspense fallback={<MapSkeleton className={rest.className} />}>
        <MapView route={route} stops={stops} timezone={timezone} {...rest} />
      </Suspense>
    </ErrorBoundary>
  );
}

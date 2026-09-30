// The map itself (Leaflet, its CSS, the polyline decoder) stays in the MapView chunk. Import only
// LazyMapView from here; never import ./MapView statically or the chunk lands in the main bundle.
export { LazyMapView, prefetchMapView } from "./LazyMapView";
export type { LazyMapViewProps, MapPanelState } from "./LazyMapView";

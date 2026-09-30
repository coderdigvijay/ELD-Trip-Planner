// Tile sources (DESIGN_SYSTEM 6.1). CARTO Positron when a public tile key is configured,
// otherwise OSM standard tiles. The routing credit is always shown.
const ROUTING = "Routing © openrouteservice.org by HeiGIT";

export interface TileSource {
  id: "carto" | "osm";
  url: string;
  attribution: string;
  subdomains: string;
}

export function cartoSource(key: string): TileSource {
  return {
    id: "carto",
    url: `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(key)}`,
    attribution: `© OpenStreetMap contributors, © CARTO | ${ROUTING}`,
    subdomains: "abcd",
  };
}

export const OSM_SOURCE: TileSource = {
  id: "osm",
  url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  attribution: `© OpenStreetMap contributors | ${ROUTING}`,
  subdomains: "abc",
};

/** First source to try, and the one to fall back to when it fails to load tiles. */
export function tileSources(cartoKey: string | undefined): TileSource[] {
  const key = cartoKey?.trim();
  return key ? [cartoSource(key), OSM_SOURCE] : [OSM_SOURCE];
}

export const MAX_ZOOM = 18;

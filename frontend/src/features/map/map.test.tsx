import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { days, must, plan, stops, timeline } from "../results/__fixtures__/multiDayTrip";
import { StopTimeline } from "../results/StopTimeline";
import { glyphSpec } from "../results/glyphSpec";
import { groupStops } from "./markerGroups";
import { stopGlyphSvg } from "./glyphSvg";
import { tileSources } from "./tiles";

// The Leaflet boundary is mocked: react-leaflet becomes plain elements that expose what MapView passes in.
const fitBounds = vi.fn();
const fakeMap = {
  fitBounds,
  getContainer: () => document.createElement("div"),
  getZoom: () => 5,
  setView: vi.fn(),
  flyTo: vi.fn(),
  invalidateSize: vi.fn(),
  attributionControl: { setPrefix: vi.fn() },
  scrollWheelZoom: { enable: vi.fn(), disable: vi.fn() },
};

vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
);

vi.mock("leaflet/dist/leaflet.css", () => ({}));
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children, ref }: { children: ReactNode; ref?: (m: unknown) => void }) => {
    ref?.(fakeMap);
    return <div data-testid="map">{children}</div>;
  },
  TileLayer: ({ attribution, url }: { attribution: string; url: string }) => (
    <div data-testid="tiles" data-url={url}>
      {attribution}
    </div>
  ),
  Polyline: ({
    positions,
    className,
    dashArray,
    weight,
  }: {
    positions: number[][];
    className: string;
    dashArray?: string;
    weight: number;
  }) => (
    // Direct props, as react-leaflet only applies className/weight at construction.
    <div
      data-testid={`path-${className}`}
      data-points={positions.length}
      data-dash={dashArray ?? ""}
      data-weight={weight}
    />
  ),
  Marker: ({
    children,
    eventHandlers,
    icon,
  }: {
    children: ReactNode;
    eventHandlers: { click: () => void };
    icon: { options: { html: string } };
  }) => (
    <button
      type="button"
      data-testid="marker"
      data-html={icon.options.html}
      onClick={eventHandlers.click}
    >
      {children}
    </button>
  ),
  Tooltip: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  useMap: () => fakeMap,
  useMapEvents: () => fakeMap,
}));

const { default: MapView } = await import("./MapView");
const { LazyMapView } = await import("./LazyMapView");

const props = { route: plan.route, stops, timezone: plan.trip.timezone };

describe("marker grouping and glyphs", () => {
  it("merges end into the dropoff marker and lists every event", () => {
    const groups = groupStops(stops);
    expect(groups).toHaveLength(5);
    const merged = groups.find((g) => g.id === "s5");
    expect(merged?.stops.map((s) => s.id)).toEqual(["s5", "s6"]);
  });

  it("gives every kind a distinct shape signature, so color is never the only cue", () => {
    const shapes = (
      ["start", "pickup", "dropoff", "fuel", "break", "rest", "restart"] as const
    ).map((kind) => {
      const spec = glyphSpec(kind);
      const tags = spec.nodes.map((n) => n.tag).join("+");
      const text = spec.nodes.map((n) => n.text ?? "").join("");
      return `${tags}|${text}|${spec.size}`;
    });
    // pickup and dropoff differ by their letter; everything else by geometry or size.
    expect(new Set(shapes).size).toBe(shapes.length);
  });

  it("serializes glyphs to a safe SVG string with no script or event attributes", () => {
    const { html } = stopGlyphSvg("fuel");
    expect(html.startsWith("<svg")).toBe(true);
    expect(html).not.toMatch(/<script|onerror|onload/i);
  });
});

describe("tile sources", () => {
  it("uses CARTO with the key when set, OSM otherwise, and always credits routing", () => {
    const withKey = tileSources("abc123");
    expect(withKey.map((s) => s.id)).toEqual(["carto", "osm"]);
    expect(withKey[0]?.url).toContain("light_all/{z}/{x}/{y}{r}.png?key=abc123");
    const noKey = tileSources("");
    expect(noKey.map((s) => s.id)).toEqual(["osm"]);
    for (const s of [...withKey, ...noKey]) {
      expect(s.attribution).toContain("© OpenStreetMap contributors");
      expect(s.attribution).toContain("Routing © openrouteservice.org by HeiGIT");
    }
  });
});

describe("MapView", () => {
  it("draws both legs (casing and line), the first dashed, and fits the API bounds", () => {
    render(<MapView {...props} />);
    const lines = screen.getAllByTestId("path-route-line");
    expect(lines.map((l) => l.dataset.points)).toEqual(["3", "5"]);
    expect(lines.map((l) => l.dataset.dash)).toEqual(["8 6", ""]);
    expect(screen.getAllByTestId("path-route-casing")).toHaveLength(2);
    expect(lines.map((l) => l.dataset.weight)).toEqual(["4", "4"]);
    expect(screen.getAllByTestId("path-route-casing").map((l) => l.dataset.weight)).toEqual([
      "7",
      "7",
    ]);
    expect(screen.getByTestId("tiles")).toHaveTextContent(
      "Routing © openrouteservice.org by HeiGIT",
    );
    expect(fitBounds).toHaveBeenCalledWith(
      [
        [37.54072, -79.8],
        [40.73566, -74.17237],
      ],
      expect.objectContaining({ padding: [32, 32] }),
    );
  });

  it("skips a zero-length leg and leaves it out of the legend", () => {
    const route = {
      ...plan.route,
      legs: [{ ...must(plan.route.legs[0]), polyline: "" }, must(plan.route.legs[1])],
    };
    render(<MapView {...props} route={route} />);
    expect(screen.getAllByTestId("path-route-line")).toHaveLength(1);
    const legend = screen.getByRole("list", { name: "Map legend" });
    expect(within(legend).queryByText("To pickup")).not.toBeInTheDocument();
    expect(within(legend).getByText("To dropoff")).toBeInTheDocument();
  });

  it("lists only the stop types present in the legend", () => {
    render(<MapView {...props} />);
    const legend = screen.getByRole("list", { name: "Map legend" });
    const items = within(legend)
      .getAllByRole("listitem")
      .map((li) => li.lastChild?.textContent);
    expect(items).toEqual([
      "Start",
      "Pickup",
      "Dropoff",
      "Fuel",
      "10-hr rest",
      "To pickup",
      "To dropoff",
    ]);
  });

  it("renders one marker per place with a +1 badge on the merged one", () => {
    render(<MapView {...props} />);
    const markers = screen.getAllByTestId("marker");
    expect(markers).toHaveLength(5);
    expect(
      markers
        .filter((m) => m.dataset.html?.includes("stop-marker__badge"))
        .map((m) => m.dataset.html),
    ).toHaveLength(1);
  });

  it("selects the primary stop when a marker is clicked", async () => {
    const user = userEvent.setup();
    const onSelectStop = vi.fn();
    render(<MapView {...props} onSelectStop={onSelectStop} />);
    const dropoff = screen
      .getAllByTestId("marker")
      .find((m) => m.textContent.includes("Released from duty"));
    await user.click(must(dropoff));
    expect(onSelectStop).toHaveBeenCalledWith("s5");
  });

  it("does not put an API string into marker HTML", () => {
    const hostile = stops.map((s) => ({ ...s, label: '<img src=x onerror="alert(1)">' }));
    render(<MapView {...props} stops={hostile} />);
    for (const m of screen.getAllByTestId("marker"))
      expect(m.dataset.html).not.toContain("onerror");
  });
});

describe("list, map and log sync", () => {
  function Harness({ onSelectDay }: { onSelectDay: (n: number) => void }) {
    const [selected, setSelected] = useState<string | null>(null);
    return (
      <>
        <MapView {...props} selectedStopId={selected} onSelectStop={setSelected} />
        <StopTimeline
          state={{
            status: "ready",
            stops,
            timeline,
            days,
            timezone: plan.trip.timezone,
            counts: plan.summary.counts,
          }}
          selectedStopId={selected}
          onSelectStop={setSelected}
          onSelectDay={onSelectDay}
        />
      </>
    );
  }

  it("a row click and a marker click drive the same selection, Escape clears it", async () => {
    const user = userEvent.setup();
    const onSelectDay = vi.fn();
    render(<Harness onSelectDay={onSelectDay} />);

    await user.click(screen.getByRole("button", { name: /Fuel, near Hagerstown/ }));
    expect(screen.getByRole("button", { name: /Fuel, near Hagerstown/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(onSelectDay).toHaveBeenLastCalledWith(2);

    // A marker click moves the highlight to its timeline row (the merged marker selects the dropoff).
    const dropoffMarker = screen
      .getAllByTestId("marker")
      .find((m) => m.textContent.includes("Released from duty"));
    await user.click(must(dropoffMarker));
    expect(screen.getByRole("button", { name: /Dropoff, Newark/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: /Fuel, near Hagerstown/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: /Dropoff, Newark/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});

describe("LazyMapView", () => {
  it("shows the fixed-height skeleton while loading without loading the chunk", () => {
    render(<LazyMapView state={{ status: "loading" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading map");
    expect(screen.getByRole("region", { name: "Route", busy: true })).toBeInTheDocument();
  });

  it("renders nothing for empty and error", () => {
    const { container, rerender } = render(<LazyMapView state={{ status: "empty" }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<LazyMapView state={{ status: "error" }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("loads the chunk for ready data", async () => {
    render(<LazyMapView state={{ status: "ready", ...props }} />);
    expect(await screen.findByTestId("map")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fit route" })).toBeInTheDocument();
  });
});

import { glyphSpec, type SvgNode } from "../results/glyphSpec";
import type { StopKind } from "../results/types";

// Every string below is a constant from glyphSpec or a number. API text never reaches this
// file, but attribute values and text are escaped anyway so a future edit cannot open an XSS hole.
const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
const escape = (value: string | number): string =>
  String(value).replace(/[&<>"]/g, (c) => ESCAPES[c] ?? c);

function serialize(node: SvgNode): string {
  const attrs = Object.entries(node.attrs)
    .map(([name, value]) => ` ${name}="${escape(value)}"`)
    .join("");
  const inner =
    (node.children ?? []).map(serialize).join("") + (node.text ? escape(node.text) : "");
  return `<${node.tag}${attrs}>${inner}</${node.tag}>`;
}

/** The marker drawing as an SVG string for a Leaflet divIcon (same spec as the React StopGlyph). */
export function stopGlyphSvg(kind: StopKind): { html: string; size: number } {
  const spec = glyphSpec(kind);
  const html = `<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false" width="${spec.size}" height="${spec.size}" viewBox="0 0 ${spec.size} ${spec.size}">${spec.nodes.map(serialize).join("")}</svg>`;
  return { html, size: spec.size };
}

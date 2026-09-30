import { createElement, type ReactNode } from "react";

import { glyphSpec, type SvgNode } from "./glyphSpec";
import type { StopKind } from "./types";

// React attribute names for the few SVG attributes whose casing differs.
const REACT_ATTR: Record<string, string> = {
  class: "className",
  "stroke-width": "strokeWidth",
  "stroke-linecap": "strokeLinecap",
  "stroke-linejoin": "strokeLinejoin",
  "text-anchor": "textAnchor",
  "dominant-baseline": "dominantBaseline",
  "font-size": "fontSize",
  "font-weight": "fontWeight",
  "paint-order": "paintOrder",
};

function toElement(node: SvgNode, key: number): ReactNode {
  const props: Record<string, string | number> = { key };
  for (const [name, value] of Object.entries(node.attrs)) props[REACT_ATTR[name] ?? name] = value;
  const children: ReactNode[] = (node.children ?? []).map(toElement);
  if (node.text !== undefined) children.push(node.text);
  return createElement(node.tag, props, ...children);
}

export interface StopGlyphProps {
  kind: StopKind;
  /** Rendered pixel size. Defaults to the marker size; the legend uses 16, the timeline 20. */
  size?: number;
  className?: string;
}

/** The same drawing as the map marker (glyphSpec is the single source). Decorative: the label beside it names it. */
export function StopGlyph({ kind, size, className }: StopGlyphProps) {
  const spec = glyphSpec(kind);
  const px = size ?? spec.size;
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={px}
      height={px}
      viewBox={`0 0 ${spec.size} ${spec.size}`}
      className={className}
    >
      {spec.nodes.map(toElement)}
    </svg>
  );
}

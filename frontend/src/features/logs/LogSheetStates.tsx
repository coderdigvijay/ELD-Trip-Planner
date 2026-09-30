import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { BLANK_FORM } from "./BlankForm";
import { VIEW_H, VIEW_W } from "./layout";
import { SURFACE } from "./tokens";

/** Empty state: the real blank form at 50 percent, decorative (the caption carries the meaning). */
export function BlankSheetPreview() {
  return (
    <svg
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      aria-hidden="true"
      focusable="false"
      className="block h-auto w-full max-w-[1200px] opacity-50"
      style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}` }}
    >
      <rect width={VIEW_W} height={VIEW_H} fill={SURFACE} />
      {BLANK_FORM}
    </svg>
  );
}

/** Loading state: tab and sheet placeholders at the sheet's aspect ratio. No spinner, no shimmer. */
export function LogSheetSkeleton() {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3">
      <span className="sr-only">Loading log sheets</span>
      <div className="flex gap-2" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-9 w-28 animate-pulse rounded-sm bg-surface-sunk motion-reduce:animate-none"
          />
        ))}
      </div>
      <div
        aria-hidden="true"
        className="w-full max-w-[1200px] animate-pulse rounded-sm bg-surface-sunk motion-reduce:animate-none"
        style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}` }}
      />
    </div>
  );
}

/** Inline warning in the page palette (icon + text, never color alone). */
export function LogNotice({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-warn bg-warn-tint p-3 text-base text-ink"
    >
      <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-warn" />
      <div>{children}</div>
    </div>
  );
}

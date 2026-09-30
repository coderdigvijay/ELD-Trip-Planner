import { useId, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const SKELETON_ROWS = 8;

interface StopsFrameProps {
  busy?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * The Stops card shell. Fixed height from lg (h-120, h-100 at xl, DESIGN_SYSTEM 3.6) so the Daily
 * logs row never moves when the stop count arrives; below lg the card grows with its list.
 * It lives outside the lazy results chunk so the fallback and the loaded card share one frame.
 */
export function StopsFrame({ busy, className, children }: StopsFrameProps) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      aria-busy={busy}
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-md border border-rule bg-surface p-4 md:p-5 lg:h-120 xl:h-100",
        className,
      )}
    >
      <h2 id={headingId} className="label-caps">
        Stops
      </h2>
      {children}
    </section>
  );
}

export function StopsSkeletonRows() {
  return (
    <div className="mt-3 min-h-0 flex-1 space-y-3 overflow-hidden" aria-hidden="true">
      {Array.from({ length: SKELETON_ROWS }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}

/** The Stops card while the results chunk downloads. */
export function StopsFallback() {
  return (
    <StopsFrame busy>
      <StopsSkeletonRows />
    </StopsFrame>
  );
}

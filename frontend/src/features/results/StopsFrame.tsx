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
 * The Stops card shell. From xl it sits beside the Route card and takes the row height (its content is
 * absolutely placed, so a long list scrolls inside instead of stretching the row). At lg it stacks
 * under the map and shrinks to its list up to 30 rem; below lg it grows with the list.
 * It lives outside the lazy results chunk so the fallback and the loaded card share one frame.
 */
export function StopsFrame({ busy, className, children }: StopsFrameProps) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      aria-busy={busy}
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-md border border-rule bg-surface lg:max-h-120 xl:relative xl:max-h-none",
        className,
      )}
    >
      <div className="flex min-h-0 flex-1 flex-col p-4 md:p-5 xl:absolute xl:inset-0">
        <h2 id={headingId} className="label-caps">
          Stops
        </h2>
        {children}
      </div>
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

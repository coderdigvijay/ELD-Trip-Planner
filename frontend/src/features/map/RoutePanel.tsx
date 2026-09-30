import { useId, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface RoutePanelProps {
  /** Right side of the heading row (the Fit route button, or its skeleton). */
  action: ReactNode;
  children: ReactNode;
  /** Under the frame: the legend and the tile warning. */
  footer?: ReactNode;
  busy?: boolean;
  onKeyDown?: (event: KeyboardEvent<HTMLElement>) => void;
  className?: string;
}

/**
 * The route panel shell. It lives outside the lazy chunk so the skeleton and the loaded map share
 * one frame: same heading row, same minimum heights (280 / 360 / 400 px, the map grows to fill a taller row), so nothing shifts (CLS).
 */
export function RoutePanel({
  action,
  children,
  footer,
  busy,
  onKeyDown,
  className,
}: RoutePanelProps) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      aria-busy={busy}
      onKeyDown={onKeyDown}
      className={cn("flex flex-col rounded-md border border-rule bg-surface p-4 md:p-5", className)}
    >
      <div className="flex min-h-8 flex-wrap items-center justify-between gap-3">
        <h2 id={headingId} className="label-caps">
          Route
        </h2>
        {action}
      </div>
      <div className="relative mt-3 min-h-70 flex-1 overflow-hidden rounded-md border border-rule bg-surface-sunk lg:min-h-90 xl:min-h-100">
        <div className="absolute inset-0">{children}</div>
      </div>
      <div className="mt-3 min-h-10">{footer}</div>
    </section>
  );
}

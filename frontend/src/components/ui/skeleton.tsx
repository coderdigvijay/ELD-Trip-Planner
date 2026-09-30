import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Fixed-size placeholder. Opacity pulse only, no shimmer (DESIGN_SYSTEM 4.2). */
function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      aria-hidden="true"
      data-slot="skeleton"
      className={cn("animate-pulse rounded-sm bg-surface-sunk", className)}
      {...props}
    />
  );
}

export { Skeleton };

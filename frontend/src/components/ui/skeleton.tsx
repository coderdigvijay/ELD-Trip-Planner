import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Fixed-size placeholder. Opacity pulse 0.6 to 1 over 1.2 s, static under reduced motion. No shimmer, no shimmer (DESIGN_SYSTEM 4.2). */
function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      aria-hidden="true"
      data-slot="skeleton"
      className={cn(
        "animate-skeleton rounded-sm bg-surface-sunk motion-reduce:animate-none",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };

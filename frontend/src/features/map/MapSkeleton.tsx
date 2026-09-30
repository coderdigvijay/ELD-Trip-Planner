import { Skeleton } from "@/components/ui/skeleton";
import { RoutePanel } from "./RoutePanel";

/** Fixed-height frame shown while the map chunk loads (DESIGN_SYSTEM 6.6). */
export function MapSkeleton({ className }: { className?: string }) {
  return (
    <RoutePanel
      busy
      className={className}
      action={<Skeleton className="h-8 w-20" />}
      footer={<Skeleton className="h-5 w-3/4" />}
    >
      <div role="status" className="flex size-full items-center justify-center text-sm text-ink-3">
        <span className="sr-only">Loading map</span>
      </div>
    </RoutePanel>
  );
}

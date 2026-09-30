import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";
import { BlankSheetPreview } from "./LogSheetStates";

/**
 * The Daily logs frame and its first-visit state. Kept apart from DailyLogs so the app shell can
 * paint them without loading the sheet renderer (the sheets load after the first plan).
 */
export function LogsSection({ children, className }: { children: ReactNode; className?: string }) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      className={cn("@container rounded-md border border-rule bg-surface p-4 md:p-5", className)}
    >
      <h2 id={headingId} className="mb-3 label-caps">
        Daily logs
      </h2>
      {children}
    </section>
  );
}

export function EmptyLogs() {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-base text-ink-2">Log sheets appear here, one per day of the trip.</p>
      <BlankSheetPreview />
    </div>
  );
}

import { Skeleton } from "@/components/ui/skeleton";

const FIGURE_COUNT = 5;

/** Placeholder for the five summary figures. Same box (min-h-19.5) and grid as the loaded figures. */
export function SummarySkeleton() {
  return (
    <div className="mt-3 min-h-19.5" aria-hidden="true">
      <div className="grid grid-cols-2 gap-x-4 gap-y-4 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: FIGURE_COUNT }, (_, i) => (
          <div key={i} className="flex flex-col">
            {/* Line heights of the loaded figure: value 24 px (28 from md), label 18 px. */}
            <Skeleton className="h-6 w-24 md:h-7" />
            <Skeleton className="h-4.5 w-20" />
          </div>
        ))}
      </div>
      <Skeleton className="mt-3 h-4.5 w-64 max-w-full" />
    </div>
  );
}

/**
 * The Summary card while the results chunk downloads. It lives outside the lazy chunk and has the
 * same heading row height as the loaded card (the Assumptions button is 32 px), so nothing shifts.
 */
export function SummaryFallback() {
  return (
    <section
      aria-busy="true"
      aria-label="Summary"
      className="rounded-md border border-rule bg-surface p-4 md:p-5"
    >
      <div className="flex min-h-8 flex-wrap items-center justify-between gap-3">
        <h2 className="label-caps">Summary</h2>
      </div>
      <div role="status">
        <span className="sr-only">Loading results</span>
        <SummarySkeleton />
      </div>
    </section>
  );
}

import { Button } from "@/components/ui/button";

interface EmptyGuidanceProps {
  onFillExample: () => void;
}

const STEPS = [
  "Enter where the truck is now, the pickup and the dropoff. Pick a suggestion or type City, ST.",
  "Enter the on-duty hours already used in the current 70 hr / 8 day cycle.",
  "Plan trip. You get a route map, every required stop and rest, and one filled-in log sheet per day.",
] as const;

/** First-visit guidance (DESIGN_SYSTEM 4.1). The blank log sheet preview lives in DailyLogs. */
export function EmptyGuidance({ onFillExample }: EmptyGuidanceProps) {
  return (
    <section
      aria-labelledby="guidance-heading"
      className="rounded-md border border-rule bg-surface p-4 md:p-5"
    >
      <h2 id="guidance-heading" className="text-xl font-semibold">
        Plan a trip to get its route, stops and daily logs.
      </h2>
      <ol className="mt-4 flex max-w-prose flex-col gap-3 text-lg text-foreground">
        {STEPS.map((step, index) => (
          <li key={step} className="flex gap-3">
            <span
              aria-hidden="true"
              className="w-5 shrink-0 font-mono text-base font-medium text-ink-3 num"
            >
              {index + 1}.
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <div className="mt-5 flex flex-wrap items-center gap-4">
        <Button variant="secondary" onClick={onFillExample}>
          Fill an example trip
        </Button>
        <p className="text-base text-ink-2">
          Fills the form only. Nothing is sent until you press Plan trip.
        </p>
      </div>
      <p className="mt-5 border-t border-rule pt-4 text-base text-ink-2">
        The planning assumptions are listed with the results.
      </p>
    </section>
  );
}

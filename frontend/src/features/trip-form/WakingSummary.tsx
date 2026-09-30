import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useId } from "react";
import { useSecondClock } from "@/lib/useSecondClock";

interface WakingSummaryProps {
  /** Epoch seconds of the click. The counter shows real elapsed time. */
  startedAtS: number;
  onCancel: () => void;
}

/** "Waking the server" sub-state, shown in the Summary box while a plan waits on a cold instance (4.3). */
export function WakingSummary({ startedAtS, onCancel }: WakingSummaryProps) {
  const headingId = useId();
  const clock = useSecondClock(true);
  const waited = Math.max(0, clock - startedAtS);
  return (
    <section
      aria-labelledby={headingId}
      aria-busy="true"
      className="rounded-md border border-rule bg-surface p-4 md:p-5"
    >
      <div className="flex min-h-8 items-center">
        <h2 id={headingId} className="label-caps">
          Summary
        </h2>
      </div>
      <div className="mt-3 min-h-24">
        {/* The live region announces the title once; the ticking counter below stays silent. */}
        <p role="status" className="sr-only">
          Starting the server. The first plan may take up to a minute.
        </p>
        <Alert
          variant="info"
          role="group"
          aria-label="Starting the server"
          title="Starting the server"
          action={
            <>
              <Button variant="secondary" size="sm" onClick={onCancel}>
                Cancel
              </Button>
              <span className="font-mono text-base text-ink-2 num" aria-hidden="true">
                Waiting {waited} s
              </span>
            </>
          }
        >
          The free host sleeps when idle. The first plan may take up to a minute.
        </Alert>
      </div>
    </section>
  );
}

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useSecondClock } from "@/lib/useSecondClock";

import type { AlertFailure } from "./describeError";
import type { TripFieldName } from "./schema";

interface PlanAlertProps {
  failure: AlertFailure;
  /** Epoch seconds when the failure arrived; the countdown runs from here. */
  failedAtS: number | null;
  showingPrevious: boolean;
  onRetry: () => void;
  onEdit: (field: TripFieldName) => void;
}

/** Results-level error or warning (DESIGN_SYSTEM 4.5). The action depends on the error code only. */
export function PlanAlert({
  failure,
  failedAtS,
  showingPrevious,
  onRetry,
  onEdit,
}: PlanAlertProps) {
  const { action } = failure;
  const countdownS = action.type === "retry" ? action.countdownS : null;
  const counting = countdownS !== null && failedAtS !== null;
  const clock = useSecondClock(counting);
  const remaining = counting ? Math.max(0, countdownS - (clock - failedAtS)) : 0;
  const waiting = counting && remaining > 0;

  let actionNode;
  if (action.type === "retry") {
    actionNode = (
      <Button
        variant="secondary"
        disabled={waiting}
        focusableWhenDisabled
        className="min-w-28"
        onClick={onRetry}
      >
        Try again
      </Button>
    );
  } else if (action.type === "edit") {
    const field = action.field;
    actionNode = (
      <Button
        variant="secondary"
        onClick={() => {
          onEdit(field);
        }}
      >
        {action.label}
      </Button>
    );
  }

  const countdownText = counting
    ? remaining > 0
      ? `You can plan again in ${String(remaining)} s.`
      : "You can plan again now."
    : null;

  return (
    <div className="flex flex-col gap-3">
      <Alert
        variant={failure.tone}
        // A ticking countdown must not be re-announced every second: it gets a quiet group role
        // plus one sr-only status line that changes only at the start and at zero.
        role={counting ? "group" : undefined}
        title={failure.title}
        action={actionNode}
      >
        {failure.body ? (
          <p>
            {failure.body}
            {failure.requestId ? (
              <>
                {" "}
                <code className="font-mono text-base text-foreground">{failure.requestId}</code>.
              </>
            ) : null}
          </p>
        ) : null}
        {countdownText ? (
          <p className="font-mono text-base text-foreground num" aria-hidden="true">
            {countdownText}
          </p>
        ) : null}
      </Alert>
      {counting ? (
        <p role="status" className="sr-only">
          {remaining > 0
            ? `${failure.title}. You can plan again in ${String(countdownS)} seconds.`
            : "You can plan again now."}
        </p>
      ) : null}
      {showingPrevious ? <p className="text-base text-ink-2">Showing your previous trip.</p> : null}
    </div>
  );
}

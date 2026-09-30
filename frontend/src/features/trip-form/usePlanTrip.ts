import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { isAbortError, NetworkError } from "@/services/errors";
import { planTrip, type PlanTripRequest, type PlanTripResponse } from "@/services/trips";

import { describePlanError, type PlanFailure } from "./describeError";
import { healthQueryOptions } from "./serverHealth";

/** The whole submit, click to result, is abandoned after this long (DESIGN_SYSTEM 4.3). */
export const SUBMIT_DEADLINE_MS = 90_000;

function abortError(signal: AbortSignal): Error {
  const reason: unknown = signal.reason;
  if (reason instanceof Error && reason.name === "TimeoutError") {
    return new NetworkError("timeout", reason);
  }
  return reason instanceof Error ? reason : new DOMException("Aborted", "AbortError");
}

/**
 * If the warm-up ping is in flight, wait for it (never race a cold instance). A failed ping does not
 * block: the plan response is the source of truth. Resolves early, by rejecting, when `signal` aborts.
 */
function waitForWarmup(queryClient: QueryClient, signal: AbortSignal): Promise<void> {
  if (queryClient.getQueryState(healthQueryOptions.queryKey)?.fetchStatus !== "fetching") {
    return Promise.resolve();
  }
  const warm = queryClient.query(healthQueryOptions).then(
    () => undefined,
    () => undefined,
  );
  return new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      reject(abortError(signal));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener("abort", onAbort, { once: true });
    void warm.then(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    });
  });
}

interface PlanState {
  /** The last successful plan. Kept while a new one loads so an error can restore it (4.5). */
  lastPlan: PlanTripResponse | null;
  failure: PlanFailure | null;
  /** Epoch seconds when the failure arrived, for countdowns. */
  failedAtS: number | null;
}

interface Options {
  onFailure?: (failure: PlanFailure) => void;
  onSuccess?: (plan: PlanTripResponse, request: PlanTripRequest) => void;
}

export function usePlanTrip({ onFailure, onSuccess }: Options = {}) {
  const queryClient = useQueryClient();
  const controllerRef = useRef<AbortController | null>(null);
  const busyRef = useRef(false);
  const [state, setState] = useState<PlanState>({ lastPlan: null, failure: null, failedAtS: null });

  const mutation = useMutation({
    mutationFn: async (request: PlanTripRequest) => {
      const controller = new AbortController();
      controllerRef.current = controller;
      const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(SUBMIT_DEADLINE_MS)]);
      await waitForWarmup(queryClient, signal);
      return planTrip(request, signal);
    },
    onSettled: () => {
      busyRef.current = false;
    },
    onSuccess: (plan, request) => {
      setState({ lastPlan: plan, failure: null, failedAtS: null });
      onSuccess?.(plan, request);
    },
    onError: (error) => {
      if (isAbortError(error)) return; // the user pressed Cancel
      const failure = describePlanError(error);
      setState((previous) => ({
        ...previous,
        failure,
        failedAtS: Math.floor(Date.now() / 1000),
      }));
      onFailure?.(failure);
    },
  });

  const submit = useCallback(
    (request: PlanTripRequest) => {
      if (busyRef.current) return; // a pending submit ignores further presses
      busyRef.current = true;
      setState((previous) => ({ ...previous, failure: null, failedAtS: null }));
      mutation.mutate(request);
    },
    [mutation],
  );

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    busyRef.current = false;
    mutation.reset();
  }, [mutation]);

  return {
    submit,
    cancel,
    isPending: mutation.isPending,
    submittedAtS:
      mutation.isPending && mutation.submittedAt > 0
        ? Math.floor(mutation.submittedAt / 1000)
        : null,
    plan: mutation.data ?? state.lastPlan,
    lastPlan: state.lastPlan,
    failure: state.failure,
    failedAtS: state.failedAtS,
  };
}

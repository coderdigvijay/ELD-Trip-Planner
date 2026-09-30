import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback, useState } from "react";
import { flushSync } from "react-dom";
import { useForm } from "react-hook-form";

import type { FieldProblem } from "./describeError";
import { decodeShare } from "./share";
import {
  defaultTripValues,
  DEFAULT_START_TIME,
  EXAMPLE_TRIP,
  tripFormSchema,
  type TripFieldName,
  type TripFormValues,
} from "./schema";

const OPTIONAL_FIELDS = /^(start_date|start_time|log_header\.)/;

function initialValues(): TripFormValues {
  return decodeShare(window.location.search) ?? defaultTripValues();
}

/** Form state for the trip form: react-hook-form + zod, validating on blur and submit. */
export function useTripForm() {
  const [initial] = useState(initialValues);
  const form = useForm<TripFormValues, unknown, TripFormValues>({
    resolver: zodResolver(tripFormSchema),
    mode: "onBlur",
    defaultValues: initial,
  });
  const [detailsOpen, setDetailsOpen] = useState(
    Boolean(initial.start_date) ||
      initial.start_time !== DEFAULT_START_TIME ||
      Object.values(initial.log_header).some(Boolean),
  );
  const { setFocus, setError, setValue, clearErrors } = form;

  /** Focus a field, opening the optional section first when it lives there. */
  const focusField = useCallback(
    (name: TripFieldName) => {
      if (OPTIONAL_FIELDS.test(name)) {
        flushSync(() => {
          setDetailsOpen(true);
        });
      }
      setFocus(name);
    },
    [setFocus],
  );

  /** Show server-side field errors under their fields and focus the first. */
  const applyProblems = useCallback(
    (problems: readonly FieldProblem[]) => {
      for (const problem of problems) {
        setError(problem.field, { type: "server", message: problem.message });
      }
      const first = problems[0];
      if (first) focusField(first.field);
    },
    [setError, focusField],
  );

  /** Fill the example trip. The form only; the user still presses Plan trip. */
  const fillExample = useCallback(() => {
    clearErrors();
    setValue("current_location", EXAMPLE_TRIP.current_location);
    setValue("pickup_location", EXAMPLE_TRIP.pickup_location);
    setValue("dropoff_location", EXAMPLE_TRIP.dropoff_location);
    setValue("current_cycle_used_hours", EXAMPLE_TRIP.current_cycle_used_hours);
  }, [clearErrors, setValue]);

  return { form, detailsOpen, setDetailsOpen, focusField, applyProblems, fillExample };
}

export type TripFormApi = ReturnType<typeof useTripForm>;

import { Info, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { Controller, type FieldErrors, type FieldPath } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { NumberField } from "@/components/ui/number-field";
import { useSecondClock } from "@/lib/useSecondClock";

import { LocationField } from "./LocationField";
import { useServerHealth } from "./serverHealth";
import {
  CYCLE_MAX,
  CYCLE_STEP,
  LOG_HEADER_LIMITS,
  START_TIME_OPTIONS,
  startDateBounds,
  type LogHeaderKey,
  type TripFormValues,
} from "./schema";
import type { TripFormApi } from "./useTripForm";

interface TripFormProps {
  api: TripFormApi;
  pending: boolean;
  onSubmit: (values: TripFormValues) => void;
  /** Ref for the submit button, so the example fill can hand focus to it. */
  submitRef?: React.Ref<HTMLButtonElement>;
  onFocusWithin?: () => void;
}

const HINT_AFTER_S = 3;

const LOG_HEADER_FIELDS: readonly { key: LogHeaderKey; label: string; hint?: string }[] = [
  { key: "driver_name", label: "Driver name" },
  { key: "carrier_name", label: "Carrier name" },
  {
    key: "main_office_address",
    label: "Main office address",
    hint: "Defaults to the current location.",
  },
  {
    key: "home_terminal_address",
    label: "Home terminal address",
    hint: "Defaults to the current location.",
  },
  { key: "truck_number", label: "Truck number" },
  { key: "trailer_number", label: "Trailer number" },
  { key: "shipping_doc", label: "Shipping document (DVL or manifest no.)" },
  { key: "shipper_commodity", label: "Shipper and commodity" },
];

function message(
  errors: FieldErrors<TripFormValues>,
  path: FieldPath<TripFormValues>,
): string | undefined {
  const [head, tail] = path.split(".");
  if (head === "log_header" && tail) {
    const nested = errors.log_header as
      Record<string, { message?: string } | undefined> | undefined;
    return nested?.[tail]?.message;
  }
  const entry = (errors as Record<string, { message?: string } | undefined>)[head ?? ""];
  return entry?.message;
}

/** Starts pending; after 3 s of waiting the cold-start hint appears, and clears when health settles. */
function StatusSlot() {
  const health = useServerHealth();
  const [startedS] = useState(() => Math.floor(Date.now() / 1000));
  const clock = useSecondClock(health.isPending);
  const waking = health.isPending && clock - startedS >= HINT_AFTER_S;
  return (
    <div role="status" aria-live="polite" className="min-h-9 text-sm text-ink-2">
      {waking ? (
        <p className="flex items-start gap-1.5">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>Server starting. The first plan may take a minute.</span>
        </p>
      ) : null}
    </div>
  );
}

export function TripForm({ api, pending, onSubmit, submitRef, onFocusWithin }: TripFormProps) {
  const { form, detailsOpen, setDetailsOpen, focusField } = api;
  const { control, register, handleSubmit, formState } = form;
  const { errors } = formState;
  const bounds = startDateBounds();

  const submit = handleSubmit(
    (values) => {
      if (pending) return;
      onSubmit(values);
    },
    (invalid) => {
      // RHF already tried to focus the first error; it cannot reach inside a closed disclosure.
      const optional = ["start_date", "start_time", "log_header"].some((key) => key in invalid);
      const required = [
        "current_location",
        "pickup_location",
        "dropoff_location",
        "current_cycle_used_hours",
      ].some((key) => key in invalid);
      if (optional && !required) {
        const headerKey = invalid.log_header
          ? LOG_HEADER_FIELDS.find(
              ({ key }) => (invalid.log_header as Record<string, unknown>)[key],
            )?.key
          : undefined;
        focusField(
          headerKey ? `log_header.${headerKey}` : invalid.start_date ? "start_date" : "start_time",
        );
      }
    },
  );

  const locationFields = [
    { name: "current_location", label: "Current location", index: "01" },
    { name: "pickup_location", label: "Pickup", index: "02" },
    { name: "dropoff_location", label: "Dropoff", index: "03" },
  ] as const;

  return (
    <form
      aria-labelledby="trip-heading"
      noValidate
      onSubmit={(event) => {
        void submit(event);
      }}
      onFocus={onFocusWithin}
      aria-busy={pending}
      className="flex flex-col gap-4"
    >
      <div className="flex flex-col gap-4 md:grid md:grid-cols-2 lg:flex lg:flex-col">
        {locationFields.map(({ name, label, index }) => (
          <Controller
            key={name}
            control={control}
            name={name}
            render={({ field, fieldState }) => (
              <Field
                label={label}
                index={index}
                error={fieldState.error?.message}
                hint={
                  typeof field.value === "string" && field.value.trim().length >= 3
                    ? "We'll look this place up when you plan."
                    : undefined
                }
                reserveHint
              >
                {(control) => (
                  <LocationField
                    id={control.id}
                    name={field.name}
                    value={field.value}
                    onChange={(next) => {
                      field.onChange(next);
                      if (fieldState.error) form.clearErrors(name);
                    }}
                    onBlur={field.onBlur}
                    inputRef={field.ref}
                    readOnly={pending}
                    invalid={control["aria-invalid"]}
                    describedBy={control["aria-describedby"]}
                  />
                )}
              </Field>
            )}
          />
        ))}
        <Controller
          control={control}
          name="current_cycle_used_hours"
          render={({ field, fieldState }) => (
            <Field
              label="Cycle used (last 8 days)"
              index="04"
              error={fieldState.error?.message}
              hint="On-duty hours already used in the current 70 hr / 8 day cycle."
            >
              {(control) => (
                <NumberField
                  id={control.id}
                  value={field.value}
                  onValueChange={(next) => {
                    field.onChange(next);
                    if (fieldState.error) form.clearErrors("current_cycle_used_hours");
                  }}
                  onBlur={field.onBlur}
                  inputRef={field.ref}
                  min={0}
                  max={CYCLE_MAX}
                  step={CYCLE_STEP}
                  largeStep={1}
                  suffix="h of 70"
                  decreaseLabel="Decrease cycle hours by 0.25"
                  increaseLabel="Increase cycle hours by 0.25"
                  readOnly={pending}
                  invalid={control["aria-invalid"]}
                  describedBy={control["aria-describedby"]}
                />
              )}
            </Field>
          )}
        />
      </div>

      <details
        open={detailsOpen}
        onToggle={(event) => {
          setDetailsOpen(event.currentTarget.open);
        }}
        className="group rounded-sm border border-rule bg-surface"
      >
        <summary className="flex min-h-11 cursor-pointer items-center gap-2 px-3 text-base font-semibold text-ink-2 select-none hover:bg-surface-sunk focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pen md:min-h-9">
          Start time and log details (optional)
        </summary>
        <div className="flex flex-col gap-4 border-t border-rule p-3">
          <Field label="Start date" optional error={message(errors, "start_date")}>
            {(control) => (
              <Input
                {...control}
                type="date"
                min={bounds.min}
                max={bounds.max}
                readOnly={pending}
                {...register("start_date")}
              />
            )}
          </Field>
          <Field label="Start time" optional error={message(errors, "start_time")}>
            {(control) => (
              <NativeSelect {...control} disabled={pending} {...register("start_time")}>
                {START_TIME_OPTIONS.map((time) => (
                  <option key={time} value={time}>
                    {time}
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
          {LOG_HEADER_FIELDS.map(({ key, label, hint }) => (
            <Field
              key={key}
              label={label}
              optional
              hint={hint}
              error={message(errors, `log_header.${key}`)}
            >
              {(control) => (
                <Input
                  {...control}
                  type="text"
                  maxLength={LOG_HEADER_LIMITS[key]}
                  readOnly={pending}
                  autoComplete="off"
                  {...register(`log_header.${key}`)}
                />
              )}
            </Field>
          ))}
        </div>
      </details>

      <div className="flex flex-col gap-2">
        <Button
          ref={submitRef}
          type="submit"
          className="w-full"
          aria-disabled={pending || undefined}
          onClick={(event) => {
            if (pending) event.preventDefault();
          }}
        >
          {pending ? (
            <>
              <LoaderCircle aria-hidden="true" className="animate-spin" />
              Planning route...
            </>
          ) : (
            "Plan trip"
          )}
        </Button>
        <StatusSlot />
      </div>
    </form>
  );
}

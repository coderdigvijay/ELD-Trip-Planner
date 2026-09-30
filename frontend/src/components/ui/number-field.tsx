import { NumberField as NumberFieldPrimitive } from "@base-ui/react/number-field";
import { Minus, Plus } from "lucide-react";
import type { Ref } from "react";

import { cn } from "@/lib/utils";

interface NumberFieldProps {
  id: string;
  value: number | null;
  onValueChange: (value: number | null) => void;
  onBlur?: () => void;
  inputRef?: Ref<HTMLInputElement>;
  min: number;
  max: number;
  step: number;
  largeStep: number;
  /** Trailing unit text, for example "h of 70". */
  suffix: string;
  decreaseLabel: string;
  increaseLabel: string;
  readOnly?: boolean;
  invalid?: true | undefined;
  describedBy?: string | undefined;
}

const stepperClasses =
  "flex size-11 shrink-0 cursor-pointer items-center justify-center border-rule-strong text-ink-2 outline-none hover:bg-surface-sunk focus-visible:z-10 data-disabled:cursor-not-allowed data-disabled:text-ink-3 md:size-9";

/** Base UI NumberField in an input-group shell: [value] suffix [-][+] (DESIGN_SYSTEM 5.1). */
export function NumberField({
  id,
  value,
  onValueChange,
  onBlur,
  inputRef,
  min,
  max,
  step,
  largeStep,
  suffix,
  decreaseLabel,
  increaseLabel,
  readOnly,
  invalid,
  describedBy,
}: NumberFieldProps) {
  return (
    <NumberFieldPrimitive.Root
      id={id}
      value={value}
      onValueChange={onValueChange}
      min={min}
      max={max}
      step={step}
      largeStep={largeStep}
      locale="en-US"
      format={{ maximumFractionDigits: 2 }}
      readOnly={readOnly}
      className="w-full"
    >
      <NumberFieldPrimitive.Group
        className={cn(
          "flex h-11 items-center overflow-hidden rounded-sm border border-input bg-surface transition-colors hover:border-ink-2 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-pen md:h-9",
          invalid && "border-danger",
          readOnly && "bg-surface-sunk",
        )}
      >
        <NumberFieldPrimitive.Input
          ref={inputRef}
          aria-invalid={invalid}
          aria-describedby={describedBy}
          onBlur={onBlur}
          inputMode="decimal"
          className="h-full w-0 min-w-0 flex-1 bg-transparent px-3 font-mono text-lg font-medium text-foreground num outline-none! md:text-base"
        />
        <span aria-hidden="true" className="pe-3 text-sm whitespace-nowrap text-ink-3">
          {suffix}
        </span>
        <NumberFieldPrimitive.Decrement
          aria-label={decreaseLabel}
          className={cn(stepperClasses, "border-s")}
        >
          <Minus aria-hidden="true" className="size-4" />
        </NumberFieldPrimitive.Decrement>
        <NumberFieldPrimitive.Increment
          aria-label={increaseLabel}
          className={cn(stepperClasses, "border-s")}
        >
          <Plus aria-hidden="true" className="size-4" />
        </NumberFieldPrimitive.Increment>
      </NumberFieldPrimitive.Group>
    </NumberFieldPrimitive.Root>
  );
}

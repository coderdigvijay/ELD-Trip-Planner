import { XCircle } from "lucide-react";
import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface FieldControlProps {
  id: string;
  "aria-describedby": string | undefined;
  "aria-invalid": true | undefined;
}

interface FieldProps {
  label: ReactNode;
  /** Small mono step number ahead of the label. Decorative. */
  index?: string;
  optional?: boolean;
  hint?: ReactNode;
  error?: string | undefined;
  /** Keep a hint row reserved so a hint appearing does not shift the layout. */
  reserveHint?: boolean;
  className?: string;
  children: (control: FieldControlProps) => ReactNode;
}

/** Wires label, hint and error ids (DESIGN_SYSTEM 5.1 Field). */
export function Field({
  label,
  index,
  optional,
  hint,
  error,
  reserveHint,
  className,
  children,
}: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy =
    [hint || reserveHint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") ||
    undefined;

  return (
    <div className={cn("flex flex-col gap-1.5", className)} data-slot="field">
      <label
        htmlFor={id}
        className="flex items-baseline gap-2 text-sm font-semibold text-foreground"
      >
        {index ? (
          <span aria-hidden="true" className="font-mono text-xs font-medium text-ink-3 num">
            {index}
          </span>
        ) : null}
        <span>
          {label}
          {optional ? <span className="font-normal text-ink-3"> (optional)</span> : null}
        </span>
      </label>
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {hint || reserveHint ? (
        <p id={hintId} className={cn("text-sm text-ink-3", reserveHint && "min-h-4.5")}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="flex items-start gap-1.5 text-sm text-danger">
          <XCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

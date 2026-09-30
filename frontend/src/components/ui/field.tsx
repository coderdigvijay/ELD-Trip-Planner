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
  /**
   * Announce the hint through aria-describedby but take it out of the layout, so a hint that comes
   * and goes never shifts the spacing between fields.
   */
  hintSrOnly?: boolean;
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
  hintSrOnly,
  className,
  children,
}: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy =
    [hint || hintSrOnly ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") ||
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
      {hint || hintSrOnly ? (
        <p id={hintId} className={cn("text-sm text-ink-3", hintSrOnly && "sr-only")}>
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

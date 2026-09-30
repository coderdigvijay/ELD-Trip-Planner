import { Input as InputPrimitive } from "@base-ui/react/input";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Shared control chrome for Input, NativeSelect, Autocomplete and NumberField (DESIGN_SYSTEM 5.1). */
export const controlClasses =
  "h-11 w-full min-w-0 rounded-sm border border-input bg-surface px-3 text-lg text-foreground outline-none transition-colors placeholder:text-ink-3 hover:border-ink-2 aria-invalid:border-danger read-only:bg-surface-sunk md:h-9 md:text-base";

function Input({ className, ...props }: ComponentProps<typeof InputPrimitive>) {
  return (
    <InputPrimitive
      data-slot="input"
      className={cn(controlClasses, typeof className === "string" ? className : undefined)}
      {...props}
    />
  );
}

export { Input };

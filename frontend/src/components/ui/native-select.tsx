import { ChevronDown } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { controlClasses } from "./input";

/** Native so phones get the OS picker (DESIGN_SYSTEM 5.1). */
function NativeSelect({ className, children, ...props }: ComponentProps<"select">) {
  return (
    <div className="relative">
      <select
        data-slot="native-select"
        className={cn(controlClasses, "cursor-pointer appearance-none pe-9", className)}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-ink-3"
      />
    </div>
  );
}

export { NativeSelect };

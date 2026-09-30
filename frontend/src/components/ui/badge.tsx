import { cva, type VariantProps } from "class-variance-authority";
import { TriangleAlert } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-sm border px-1.5 font-mono text-xs leading-5 font-semibold whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "border-rule-strong bg-surface-sunk text-ink",
        warn: "border-warn bg-warn-tint text-warn",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

type BadgeProps = ComponentProps<"span"> & VariantProps<typeof badgeVariants>;

/** Text is the meaning; the warn variant adds an icon so color is never alone (DESIGN_SYSTEM 5.1). */
function Badge({ variant, className, children, ...props }: BadgeProps) {
  return (
    <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props}>
      {variant === "warn" ? <TriangleAlert aria-hidden="true" className="size-3" /> : null}
      {children}
    </span>
  );
}

export { Badge };

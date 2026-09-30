import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Variants and sizes follow DESIGN_SYSTEM 5.1. Focus ring: 2 px pen, 2 px offset.
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-sm border border-transparent text-base font-semibold whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:border-rule disabled:bg-surface-sunk disabled:text-ink-3 aria-disabled:cursor-not-allowed aria-disabled:border-rule aria-disabled:bg-surface-sunk aria-disabled:text-ink-3 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground hover:bg-ink-2",
        secondary: "border-input bg-secondary text-secondary-foreground hover:bg-surface-sunk",
        ghost: "text-ink-2 hover:bg-surface-sunk",
        link: "text-pen underline underline-offset-4",
      },
      size: {
        default: "h-11 px-4 md:h-9",
        sm: "h-8 px-3",
        icon: "size-11 md:size-9",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

type ButtonProps = Omit<ButtonPrimitive.Props, "className"> & {
  className?: string;
} & VariantProps<typeof buttonVariants>;

function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}

export { Button, buttonVariants };

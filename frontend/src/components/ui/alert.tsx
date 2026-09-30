import { cva, type VariantProps } from "class-variance-authority";
import { Info, TriangleAlert, XCircle } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

const alertVariants = cva("flex gap-3 rounded-md border border-s-4 p-3 md:p-4", {
  variants: {
    variant: {
      danger: "border-danger bg-danger-tint",
      warn: "border-warn bg-warn-tint",
      info: "border-rule-strong bg-surface",
    },
  },
  defaultVariants: { variant: "info" },
});

const ICONS = { danger: XCircle, warn: TriangleAlert, info: Info } as const;
const ICON_TONE = { danger: "text-danger", warn: "text-warn", info: "text-ink-2" } as const;

type AlertVariant = NonNullable<VariantProps<typeof alertVariants>["variant"]>;

type AlertProps = Omit<ComponentProps<"div">, "title"> & {
  variant: AlertVariant;
  title: ReactNode;
  action?: ReactNode;
};

/** danger uses role="alert"; warn and info use role="status" (DESIGN_SYSTEM 5.1). */
function Alert({ variant, title, action, className, children, role, ...props }: AlertProps) {
  const Icon = ICONS[variant];
  return (
    <div
      role={role ?? (variant === "danger" ? "alert" : "status")}
      data-slot="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    >
      <Icon aria-hidden="true" className={cn("mt-0.5 size-5 shrink-0", ICON_TONE[variant])} />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-foreground">{title}</p>
        {children ? <div className="mt-1 text-base text-ink-2">{children}</div> : null}
        {action ? <div className="mt-3 flex flex-wrap items-center gap-3">{action}</div> : null}
      </div>
    </div>
  );
}

export { Alert };

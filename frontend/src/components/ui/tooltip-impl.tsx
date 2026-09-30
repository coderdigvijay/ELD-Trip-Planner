import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import type { ReactElement, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The Base UI Tooltip itself. Import it only through ./tooltip, which loads this file on first use:
 * the primitive costs about 30 kB gzip, too much for the first paint (DESIGN_SYSTEM 3.6, LCP).
 */

const SHOW_DELAY_MS = 400;

export interface TooltipProps {
  /** The text. Never the only place essential information lives: it also opens on keyboard focus. */
  content: ReactNode;
  /** The element that gets the tooltip; it keeps its own role and accessible name. */
  children: ReactElement<Record<string, unknown>>;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}

/** Base UI Tooltip: ink background, surface text, 12 px, shadow-md, fades in 160 ms and out in 120 ms. */
function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger render={children} delay={SHOW_DELAY_MS} />
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner side={side} sideOffset={6} className="z-50">
          <TooltipPrimitive.Popup
            className={cn(
              "max-w-xs origin-(--transform-origin) rounded-sm bg-ink px-2 py-1 text-xs text-surface shadow-md transition-[opacity,scale] duration-160 ease-standard data-ending-style:scale-98 data-ending-style:opacity-0 data-ending-style:duration-120 data-ending-style:ease-exit data-starting-style:scale-98 data-starting-style:opacity-0",
              className,
            )}
          >
            {content}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export { Tooltip };

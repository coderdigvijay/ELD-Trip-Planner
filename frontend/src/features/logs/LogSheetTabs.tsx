import { Tabs } from "@base-ui/react/tabs";
import { ChevronRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { splitDate, weekdayOf } from "./format";
import type { LogDay } from "./types";

export interface LogSheetTabsProps {
  days: readonly LogDay[];
  /** 1-based sheet index of the active tab. */
  value: number;
  onValueChange: (sheetIndex: number) => void;
  /** Buttons that sit on the right of the tab row (Print logs, Download PDF). */
  actions?: ReactNode;
  children: ReactNode;
}

function DayTab({ day }: { day: LogDay }) {
  const { mm, dd } = splitDate(day.date);
  return (
    <>
      {`Day ${day.sheet_index} · ${weekdayOf(day.date)} `}
      <span className="font-mono num">{`${mm}/${dd}`}</span>
    </>
  );
}

/** Accessible day tabs (Base UI): Left/Right activate, Home/End jump, the list scrolls when it overflows. */
export function LogSheetTabs({ days, value, onValueChange, actions, children }: LogSheetTabsProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [hiddenRight, setHiddenRight] = useState(false);

  const measure = useCallback(() => {
    const el = listRef.current;
    if (el) setHiddenRight(el.scrollWidth - el.clientWidth - el.scrollLeft > 1);
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    measure();
    el.addEventListener("scroll", measure, { passive: true });
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(el);
    return () => {
      el.removeEventListener("scroll", measure);
      observer?.disconnect();
    };
  }, [measure, days.length]);

  useEffect(() => {
    // Instant and manual on purpose: scrollIntoView would also move the browser's sequential focus
    // starting point, so the first Tab press would skip the tab list.
    const list = listRef.current;
    const active = list?.querySelector<HTMLElement>("[data-active]");
    if (!list || !active) return;
    if (active.offsetLeft < list.scrollLeft) list.scrollLeft = active.offsetLeft;
    else if (active.offsetLeft + active.offsetWidth > list.scrollLeft + list.clientWidth) {
      list.scrollLeft = active.offsetLeft + active.offsetWidth - list.clientWidth;
    }
  }, [value]);

  const moreDays = () => {
    const el = listRef.current;
    if (el) el.scrollLeft += el.clientWidth;
  };

  return (
    <Tabs.Root
      value={value}
      onValueChange={(v) => {
        onValueChange(Number(v));
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Tabs.List
            ref={listRef}
            activateOnFocus
            aria-label="Log sheet days"
            className="flex min-w-0 snap-x snap-mandatory overflow-x-auto border-b border-rule"
          >
            {days.map((day) => (
              <Tabs.Tab
                key={day.sheet_index}
                value={day.sheet_index}
                className={cn(
                  "h-11 shrink-0 snap-start rounded-sm border-b-2 border-transparent px-3 text-base font-semibold whitespace-nowrap text-ink-2 outline-none md:h-9",
                  "hover:bg-surface-sunk focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  "data-active:border-pen data-active:bg-pen-tint data-active:text-ink",
                )}
              >
                <DayTab day={day} />
              </Tabs.Tab>
            ))}
          </Tabs.List>
          {hiddenRight ? (
            <Button variant="secondary" size="sm" onClick={moreDays} className="shrink-0">
              More days
              <ChevronRight aria-hidden="true" />
            </Button>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </Tabs.Root>
  );
}

export const LogSheetTabPanel = Tabs.Panel;

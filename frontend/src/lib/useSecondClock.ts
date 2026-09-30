import { useMemo, useSyncExternalStore } from "react";

function makeSubscribe(active: boolean) {
  return (notify: () => void): (() => void) => {
    if (!active) return () => undefined;
    const timer = window.setInterval(notify, 1000);
    return () => {
      window.clearInterval(timer);
    };
  };
}

const nowSeconds = () => Math.floor(Date.now() / 1000);

/** Whole seconds since the epoch, re-rendering once a second while `active` (timers, countdowns). */
export function useSecondClock(active: boolean): number {
  const subscribe = useMemo(() => makeSubscribe(active), [active]);
  return useSyncExternalStore(subscribe, nowSeconds, nowSeconds);
}

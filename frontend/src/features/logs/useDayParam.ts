import { useCallback, useEffect, useState } from "react";

const PARAM = "day";

function readDay(count: number): number {
  const raw = new URLSearchParams(window.location.search).get(PARAM);
  const n = Number(raw);
  return raw !== null && Number.isInteger(n) && n >= 1 && n <= count ? n : 1;
}

/**
 * The selected sheet lives in `?day=n` (shareable, back-button safe). Out-of-range values are replaced with 1.
 * `resetKey` changes with a new plan and returns to day 1.
 */
export function useDayParam(
  count: number,
  resetKey: unknown,
): readonly [number, (day: number) => void] {
  const [day, setDayState] = useState(() => readDay(count));
  const [prevKey, setPrevKey] = useState(resetKey);
  if (prevKey !== resetKey) {
    setPrevKey(resetKey);
    setDayState(1);
  }
  const current = Math.min(day, Math.max(1, count));

  useEffect(() => {
    const url = new URL(window.location.href);
    const param = url.searchParams.get(PARAM);
    if (param !== null && param !== String(current)) {
      url.searchParams.set(PARAM, String(current));
      window.history.replaceState(window.history.state, "", url);
    }
  }, [current]);

  useEffect(() => {
    const onPop = () => {
      setDayState(readDay(count));
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
    };
  }, [count]);

  const setDay = useCallback((next: number) => {
    setDayState(next);
    const url = new URL(window.location.href);
    url.searchParams.set(PARAM, String(next));
    window.history.pushState(window.history.state, "", url);
  }, []);

  return [current, setDay] as const;
}

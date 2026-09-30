import { cloneElement, useSyncExternalStore, type ReactElement } from "react";

import type { TooltipProps } from "./tooltip-impl";

/**
 * Tooltip (DESIGN_SYSTEM 5.1): ink bubble, 400 ms delay, opens on hover and on keyboard focus.
 *
 * The Base UI primitive is about 30 kB gzip, so it is a separate chunk. Until it has loaded, the
 * child renders as is (a tooltip is never the only home of essential text). The chunk is requested
 * on the first pointer move, key press or, failing that, a few seconds after load, and never while
 * a tooltip trigger has focus, because switching to the wrapped element would remount it.
 */
const MARK = "data-has-tooltip";
const IDLE_ARM_MS = 3000;

// Held in an object so React sees a plain value, not a component created during render.
interface LoadedTooltip {
  render: (props: TooltipProps) => ReactElement;
}
let loaded: LoadedTooltip | null = null;
let requested = false;
const listeners = new Set<() => void>();

function load(): void {
  if (requested) return;
  requested = true;
  void import("./tooltip-impl").then((module) => {
    loaded = { render: module.Tooltip };
    listeners.forEach((notify) => {
      notify();
    });
  });
}

function armWhenSafe(): void {
  const active = document.activeElement;
  if (active instanceof HTMLElement && active.hasAttribute(MARK)) {
    active.addEventListener("blur", armWhenSafe, { once: true });
    return;
  }
  load();
}

if (typeof window !== "undefined" && import.meta.env.MODE !== "test") {
  window.addEventListener("pointermove", armWhenSafe, { once: true, passive: true });
  window.addEventListener("keydown", armWhenSafe, { once: true, passive: true });
  window.addEventListener("load", () => {
    window.setTimeout(armWhenSafe, IDLE_ARM_MS);
  });
}

const subscribe = (notify: () => void) => {
  listeners.add(notify);
  return () => {
    listeners.delete(notify);
  };
};
const getLoaded = () => loaded;

export function Tooltip(props: TooltipProps) {
  const impl = useSyncExternalStore(subscribe, getLoaded, () => null);
  if (impl) return impl.render(props);
  return cloneElement(props.children, { [MARK]: "" });
}

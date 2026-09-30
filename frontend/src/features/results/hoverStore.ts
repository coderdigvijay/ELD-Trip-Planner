import { useSyncExternalStore } from "react";

/**
 * Hover sync between a stop row and its map marker (DESIGN_SYSTEM 3.6, 6.5). Hover is not React
 * state of the workspace: each row and marker subscribes to "is my stop hovered", so a hover
 * re-renders only the two elements whose answer changed, never the list or the map.
 */
export interface HoverStore {
  get: () => string | null;
  set: (stopId: string | null) => void;
  subscribe: (listener: () => void) => () => void;
}

export function createHoverStore(): HoverStore {
  let current: string | null = null;
  const listeners = new Set<() => void>();
  return {
    get: () => current,
    set: (stopId) => {
      if (stopId === current) return;
      current = stopId;
      listeners.forEach((listener) => {
        listener();
      });
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

const NEVER = () => () => undefined;

/** True while the hovered stop is one of `stopIds` (a row has one id, a merged marker several). */
export function useIsHovered(store: HoverStore | undefined, stopIds: readonly string[]): boolean {
  return useSyncExternalStore(
    store ? store.subscribe : NEVER,
    () => {
      const hovered = store?.get() ?? null;
      return hovered !== null && stopIds.includes(hovered);
    },
    () => false,
  );
}

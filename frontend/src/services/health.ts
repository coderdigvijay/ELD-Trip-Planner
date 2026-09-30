import { apiClient } from "./client";
import { NetworkError, unwrap } from "./errors";

/** Cold-start ceiling for the warm-up ping (DESIGN_SYSTEM 4.3). */
export const HEALTH_DEADLINE_MS = 75_000;

/** Warm-up ping. Only HTTP 200 with status "ok" counts as success; anything else throws. */
export async function ping(signal?: AbortSignal) {
  const guarded = AbortSignal.any([
    AbortSignal.timeout(HEALTH_DEADLINE_MS),
    ...(signal ? [signal] : []),
  ]);
  const data = await unwrap(() => apiClient.GET("/api/v1/health", { signal: guarded }));
  const status: string = data.status;
  if (status !== "ok") throw new NetworkError("bad-response");
  return data;
}

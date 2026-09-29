import { apiClient } from "./client";

// Warm-up ping. Throws on any non-2xx so TanStack Query treats it as a failure.
export async function ping(signal?: AbortSignal) {
  const { data, error } = await apiClient.GET("/api/v1/health", { signal });
  if (error) {
    throw new Error(error.error.message);
  }
  return data;
}

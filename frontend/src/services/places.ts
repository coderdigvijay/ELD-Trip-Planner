import { apiClient } from "./client";
import { unwrap } from "./errors";
import type { components } from "./api-types";

export type PlaceSuggestion = components["schemas"]["PlaceSuggestion"];

/** GET /api/v1/places/autocomplete. The TanStack Query signal cancels superseded searches. */
export async function autocomplete(q: string, signal?: AbortSignal): Promise<PlaceSuggestion[]> {
  const data = await unwrap(() =>
    apiClient.GET("/api/v1/places/autocomplete", { params: { query: { q } }, signal }),
  );
  return data.items;
}

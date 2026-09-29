import createClient from "openapi-fetch";

import type { paths } from "./api-types";

export function normalizeBaseUrl(raw: string | undefined): string {
  return (raw ?? "").trim().replace(/\/+$/, "");
}

export function createApiClient(baseUrl: string) {
  return createClient<paths>({
    baseUrl,
    // Resolve fetch per call so tests and polyfills can replace it.
    fetch: (request) => globalThis.fetch(request),
  });
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

export const apiClient = createApiClient(API_BASE_URL);

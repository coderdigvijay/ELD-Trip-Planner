import type { components } from "./api-types";

type Schemas = components["schemas"];

export type KnownErrorCode = Schemas["ErrorCode"];
export type FieldIssue = Schemas["FieldError"];

/** An error envelope from the API (API_CONTRACT section 6). `code` is an open enum. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly field: string | undefined;
  readonly details: readonly FieldIssue[];
  readonly retryAfterS: number | undefined;
  readonly requestId: string | undefined;

  constructor(init: {
    code: string;
    message: string;
    status: number;
    field?: string;
    details?: readonly FieldIssue[];
    retryAfterS?: number;
    requestId?: string;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.code = init.code;
    this.status = init.status;
    this.field = init.field;
    this.details = init.details ?? [];
    this.retryAfterS = init.retryAfterS;
    this.requestId = init.requestId;
  }
}

export type NetworkFailure = "offline" | "timeout" | "bad-response";

/** No usable response: offline, CORS, a client deadline, or a body that is not the JSON we expect. */
export class NetworkError extends Error {
  readonly reason: NetworkFailure;

  constructor(reason: NetworkFailure, cause?: unknown) {
    super(`Network failure: ${reason}`, { cause });
    this.name = "NetworkError";
    this.reason = reason;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function readDetails(value: unknown): FieldIssue[] {
  if (!Array.isArray(value)) return [];
  const issues: FieldIssue[] = [];
  for (const entry of value as unknown[]) {
    if (isRecord(entry)) {
      const field = asString(entry.field);
      const message = asString(entry.message);
      if (field !== undefined && message !== undefined) issues.push({ field, message });
    }
  }
  return issues;
}

/** Turn a non-2xx body into an ApiError, or a NetworkError when it is not our envelope (Render 502 page). */
export function errorFromBody(status: number, body: unknown): ApiError | NetworkError {
  if (!isRecord(body) || !isRecord(body.error)) return new NetworkError("bad-response");
  const inner = body.error;
  const code = asString(inner.code);
  const message = asString(inner.message);
  if (code === undefined || message === undefined) return new NetworkError("bad-response");
  return new ApiError({
    code,
    message,
    status,
    field: asString(inner.field),
    details: readDetails(inner.details),
    retryAfterS: typeof inner.retry_after_s === "number" ? inner.retry_after_s : undefined,
    requestId: asString(inner.request_id),
  });
}

// Duck-typed on `name`: the error may come from another realm (jsdom, undici), so instanceof is unreliable.
function isAbort(error: unknown): error is Error {
  return error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError");
}

interface Settled<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * Run an openapi-fetch call and normalise every failure into ApiError or NetworkError.
 * A user abort (signal aborted for any reason but a timeout) is rethrown untouched so callers can ignore it.
 */
export async function unwrap<T>(run: () => Promise<Settled<T>>): Promise<T> {
  let settled: Settled<T>;
  try {
    settled = await run();
  } catch (caught) {
    if (isAbort(caught)) {
      if (caught.name === "TimeoutError") throw new NetworkError("timeout", caught);
      throw caught;
    }
    // Body parse failures on a 2xx surface as SyntaxError; everything else is a transport failure.
    throw new NetworkError(caught instanceof SyntaxError ? "bad-response" : "offline", caught);
  }
  if (settled.response.ok && settled.data !== undefined) return settled.data;
  if (settled.response.ok) throw new NetworkError("bad-response");
  throw errorFromBody(settled.response.status, settled.error);
}

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

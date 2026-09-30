import type { ConsoleMessage, Page } from "@playwright/test";

/** An HTTP error the test expects and asserts on (URL pattern plus status). */
export interface ExpectedHttpError {
  url: RegExp;
  status: number;
}

export interface Guard {
  /** Declare one expected mocked error response; its network console line is then allowed too. */
  allowHttpError: (expected: ExpectedHttpError) => void;
  /** Requests the test aborts on purpose (Cancel), matched by URL. */
  allowAbort: (url: RegExp) => void;
  /** Everything unexpected seen so far. Must be empty at the end of a test. */
  problems: () => string[];
}

const NETWORK_LINE = /^Failed to load resource: the server responded with a status of (\d+)/;

/** Fails a test on any console error or warning, page error, failed request or HTTP status >= 400. */
export function attachGuard(page: Page): Guard {
  const problems: string[] = [];
  const allowed: ExpectedHttpError[] = [];
  const aborts: RegExp[] = [];

  const isAllowed = (url: string, status: number) =>
    allowed.some((entry) => entry.status === status && entry.url.test(url));

  page.on("console", (message: ConsoleMessage) => {
    const type = message.type();
    if (type !== "error" && type !== "warning") return;
    const text = message.text();
    const status = NETWORK_LINE.exec(text)?.[1];
    if (status !== undefined && isAllowed(message.location().url, Number(status))) return;
    problems.push(`console.${type}: ${text}`);
  });
  page.on("pageerror", (error) => {
    problems.push(`pageerror: ${error.message}`);
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (aborts.some((pattern) => pattern.test(url))) return;
    problems.push(
      `requestfailed: ${request.method()} ${url} ${request.failure()?.errorText ?? ""}`,
    );
  });
  page.on("response", (response) => {
    const status = response.status();
    if (status < 400 || isAllowed(response.url(), status)) return;
    problems.push(`http ${String(status)}: ${response.url()}`);
  });

  return {
    allowHttpError: (expected) => allowed.push(expected),
    allowAbort: (url) => aborts.push(url),
    problems: () => [...problems],
  };
}

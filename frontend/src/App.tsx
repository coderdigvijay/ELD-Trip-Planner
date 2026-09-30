import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Printer } from "lucide-react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

import { Button } from "@/components/ui/button";

import { Workspace } from "./Workspace";

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { refetchOnWindowFocus: false } },
  });
}

function ErrorFallback({ resetErrorBoundary }: FallbackProps) {
  return (
    <div role="alert" className="mx-auto max-w-xl p-6">
      <h2 className="text-xl font-semibold">The page hit an unexpected error</h2>
      <p className="mt-2 text-ink-2">
        Your trip inputs on the server are not affected. Reload or try again.
      </p>
      <Button className="mt-4" variant="secondary" onClick={resetErrorBoundary}>
        Try again
      </Button>
    </div>
  );
}

type AppProps = { queryClient?: QueryClient };

export function App({ queryClient }: AppProps) {
  const [client] = useState(() => queryClient ?? createQueryClient());
  const [hasResults, setHasResults] = useState(false);

  return (
    <QueryClientProvider client={client}>
      <div className="mx-auto flex min-h-dvh max-w-360 flex-col">
        <header className="print-hidden flex h-12 items-center justify-between gap-3 border-b border-rule px-4 md:h-14 md:px-6 lg:px-8">
          <span className="text-lg font-semibold">ELD Trip Planner</span>
          {hasResults ? (
            // Phones only: from md the Daily logs toolbar carries Print logs (DESIGN_SYSTEM 3.1).
            // The Daily logs sheets mount every day on `beforeprint`, which window.print() fires.
            <Button
              variant="secondary"
              size="sm"
              className="md:hidden"
              onClick={() => {
                window.print();
              }}
            >
              <Printer aria-hidden="true" />
              Print logs
            </Button>
          ) : null}
        </header>
        <main className="flex-1 px-4 py-6 md:px-6 lg:px-8">
          <h1 className="sr-only">ELD trip planner</h1>
          <ErrorBoundary FallbackComponent={ErrorFallback}>
            <Workspace onResultsChange={setHasResults} />
          </ErrorBoundary>
        </main>
        <footer className="border-t border-rule px-4 py-4 text-sm text-ink-3 md:px-6 lg:px-8">
          Hours are planned under 49 CFR 395, property-carrying, 70 hr / 8 day. Not a substitute for
          a certified ELD.
        </footer>
      </div>
    </QueryClientProvider>
  );
}

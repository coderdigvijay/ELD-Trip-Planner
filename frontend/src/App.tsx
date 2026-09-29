import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

import { Button } from "@/components/ui/button";
import { ping } from "@/services/health";

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { refetchOnWindowFocus: false } },
  });
}

function ServerStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => ping(signal),
    staleTime: Infinity,
    retry: 2,
  });

  let message = "";
  if (health.isPending) {
    message = "Waking the server. This can take up to a minute on the first visit.";
  } else if (health.isError) {
    message = "The server did not respond. You can still try to plan a trip.";
  }

  return (
    <p role="status" aria-live="polite" className="min-h-9 text-sm text-ink-3">
      {message}
    </p>
  );
}

function ErrorFallback({ resetErrorBoundary }: FallbackProps) {
  return (
    <div role="alert" className="mx-auto max-w-xl p-6">
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="mt-2 text-ink-2">Reload the page or try again.</p>
      <Button className="mt-4" variant="secondary" onClick={resetErrorBoundary}>
        Try again
      </Button>
    </div>
  );
}

type AppProps = { queryClient?: QueryClient };

export function App({ queryClient }: AppProps) {
  const [client] = useState(() => queryClient ?? createQueryClient());

  return (
    <QueryClientProvider client={client}>
      <ErrorBoundary FallbackComponent={ErrorFallback}>
        <header className="flex h-12 items-center border-b border-rule bg-surface px-4 md:h-14 md:px-6 lg:px-8">
          <span className="text-lg font-semibold">ELD Trip Planner</span>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6 md:px-6 lg:px-8">
          <h1 className="sr-only">ELD trip planner</h1>
          <section
            aria-labelledby="trip-heading"
            className="rounded-md border border-rule bg-card p-4 md:p-5"
          >
            <h2 id="trip-heading" className="label-caps">
              Trip
            </h2>
            <p className="mt-2 text-ink-2">
              Enter a trip to get a route map and daily log sheets. The form arrives in the next
              step.
            </p>
            <Button className="mt-4" disabled>
              Plan trip
            </Button>
            <ServerStatus />
          </section>
        </main>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

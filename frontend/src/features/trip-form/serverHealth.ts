import { queryOptions, useQuery } from "@tanstack/react-query";

import { ping } from "@/services/health";

/** One warm-up query shared by the status slot and the submit flow (DESIGN_SYSTEM 4.3). */
export const healthQueryOptions = queryOptions({
  queryKey: ["health"],
  queryFn: ({ signal }) => ping(signal),
  retry: false,
  staleTime: Infinity,
  gcTime: Infinity,
  refetchOnWindowFocus: false,
});

export function useServerHealth() {
  return useQuery(healthQueryOptions);
}

import { QueryClient } from "@tanstack/react-query";
import { Source } from "./types";

const IN_PROGRESS_STATUSES = new Set(["PENDING", "PROCESSING"]);
const SOURCE_POLL_INTERVAL_MS = 3000;

/**
 * refetchInterval for a source list: keep polling while any source is still
 * being ingested, then stop. Progress then shows however the source was added
 * (dashboard or space page) and survives a page reload mid-ingestion.
 */
export function sourceListRefetchInterval(
  sources: Pick<Source, "status">[] | undefined,
): number | false {
  const inProgress = (sources ?? []).some((source) => IN_PROGRESS_STATUSES.has(source.status));
  return inProgress ? SOURCE_POLL_INTERVAL_MS : false;
}

export async function syncDeletedSource(
  queryClient: QueryClient,
  sourceId: string,
) {
  queryClient.removeQueries({ queryKey: ["sources", sourceId], exact: true });
  queryClient.removeQueries({ queryKey: ["transcript", sourceId], exact: false });

  queryClient.setQueriesData<Source[]>(
    { queryKey: ["sources"], exact: false },
    (current) => {
      if (!Array.isArray(current)) return current;
      return current.filter((source) => source.id !== sourceId);
    },
  );

  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["sources"], exact: false }),
    queryClient.invalidateQueries({ queryKey: ["spaces"], exact: false }),
  ]);
}

import { QueryClient } from "@tanstack/react-query";
import { Source } from "./types";

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

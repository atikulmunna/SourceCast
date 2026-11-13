import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { syncDeletedSource, sourceListRefetchInterval } from "./sourceCache";
import { Source } from "./types";

function source(id: string, title: string): Source {
  return {
    id,
    source_type: "audio",
    source_url: `https://example.com/${id}.mp3`,
    canonical_url: null,
    title,
    creator_name: null,
    thumbnail_url: null,
    duration_sec: null,
    language: "auto",
    status: "PENDING",
    transcript_status: "NOT_STARTED",
    indexing_status: "NOT_STARTED",
    audio_storage_policy: "DELETE_AFTER_TRANSCRIPTION",
    created_at: "2026-06-06T00:00:00Z",
    updated_at: "2026-06-06T00:00:00Z",
  };
}

describe("syncDeletedSource", () => {
  it("removes a deleted source from detail and list caches", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    queryClient.setQueryData(["sources", "space-1"], [
      source("source-1", "Deleted"),
      source("source-2", "Kept"),
    ]);
    queryClient.setQueryData(["sources", "source-1"], source("source-1", "Deleted"));
    queryClient.setQueryData(["transcript", "source-1", 1], { segments: [] });

    await syncDeletedSource(queryClient, "source-1");

    expect(queryClient.getQueryData(["sources", "space-1"])).toEqual([
      source("source-2", "Kept"),
    ]);
    expect(queryClient.getQueryData(["sources", "source-1"])).toBeUndefined();
    expect(queryClient.getQueryData(["transcript", "source-1", 1])).toBeUndefined();
  });
});

describe("sourceListRefetchInterval", () => {
  const withStatuses = (...statuses: string[]) => statuses.map((status) => ({ status }));

  it("keeps polling while any source is still being ingested", () => {
    expect(sourceListRefetchInterval(withStatuses("READY", "PROCESSING"))).toBe(3000);
    expect(sourceListRefetchInterval(withStatuses("PENDING"))).toBe(3000);
  });

  it("stops polling once every source is settled", () => {
    expect(sourceListRefetchInterval(withStatuses("READY", "FAILED", "CANCELLED"))).toBe(false);
  });

  it("does not poll an empty or not yet loaded list", () => {
    expect(sourceListRefetchInterval([])).toBe(false);
    expect(sourceListRefetchInterval(undefined)).toBe(false);
  });
});

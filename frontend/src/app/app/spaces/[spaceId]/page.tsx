"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { Clock, FileText, Layers, Plus, Radio, Search } from "lucide-react";
import api from "@/lib/api";
import { KnowledgeSpace, Source, SourceIngestResponse } from "@/lib/types";
import { SourcePreviewModal } from "@/components/sources/SourcePreviewModal";
import { JobProgressPanel } from "@/components/jobs/JobProgressPanel";
import { SpaceChatPanel } from "@/components/spaces/SpaceChatPanel";
import { SourceComparisonPanel } from "@/components/spaces/SourceComparisonPanel";
import { SavedInsightsPanel } from "@/components/insights/SavedInsightsPanel";
import { ResearchBriefsPanel } from "@/components/briefs/ResearchBriefsPanel";

export default function SpaceDetailPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [showAddSource, setShowAddSource] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const { data: space, isLoading } = useQuery<KnowledgeSpace>({
    queryKey: ["spaces", spaceId],
    queryFn: async () => {
      const { data } = await api.get<KnowledgeSpace>(`/spaces/${spaceId}`);
      return data;
    },
  });

  const {
    data: sources = [],
    isLoading: sourcesLoading,
    refetch: refetchSources,
  } = useQuery<Source[]>({
    queryKey: ["sources", spaceId],
    queryFn: async () => {
      const { data } = await api.get<Source[]>("/sources", {
        params: { space_id: spaceId },
      });
      return data;
    },
    enabled: Boolean(spaceId),
  });

  const handleIngested = (result: SourceIngestResponse) => {
    setActiveJobId(result.job_id);
    refetchSources();
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div
          className="h-8 w-48 rounded-lg skeleton mb-4"
        />
        <div
          className="h-4 w-80 max-w-full rounded skeleton"
        />
      </div>
    );
  }

  if (!space) return null;

  return (
    <div className="p-6 sm:p-8 max-w-5xl mx-auto animate-fade-in">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <Layers size={18} style={{ color: "var(--accent)" }} />
            </div>
            <h1 className="text-2xl font-semibold">{space.name}</h1>
          </div>
          {space.description && (
            <p className="text-sm ml-12" style={{ color: "var(--text-muted)" }}>
              {space.description}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowAddSource(true)}
          className="primary-button"
        >
          <Plus size={16} />
          Add Source
        </button>
      </div>

      {activeJobId && (
        <div className="mb-6">
          <JobProgressPanel jobId={activeJobId} onDone={refetchSources} />
        </div>
      )}

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Sources
          </h2>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {sources.length} total
          </span>
        </div>

        {sourcesLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 rounded-xl skeleton" />
            ))}
          </div>
        ) : sources.length === 0 ? (
          <EmptySources onAdd={() => setShowAddSource(true)} />
        ) : (
          <div className="space-y-3">
            {sources.map((source) => (
              <SourceRow key={source.id} source={source} />
            ))}
          </div>
        )}
      </section>

      <SpaceChatPanel
        spaceId={spaceId}
        enabled={sources.some((source) => source.status === "READY" && source.indexing_status === "INDEXED")}
      />

      <SourceComparisonPanel sources={sources} spaceId={spaceId} />

      <SavedInsightsPanel spaceId={spaceId} />

      <ResearchBriefsPanel spaceId={spaceId} sources={sources} />

      <SourcePreviewModal
        open={showAddSource}
        onClose={() => setShowAddSource(false)}
        spaceId={spaceId}
        onIngested={handleIngested}
      />
    </div>
  );
}

function EmptySources({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="surface p-8 text-center">
      <Radio size={24} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
      <h3 className="font-semibold mb-1">No sources in this space</h3>
      <p className="text-sm mb-5" style={{ color: "var(--text-muted)" }}>
        Add a short video or audio source to start the research loop.
      </p>
      <button
        onClick={onAdd}
        className="primary-button"
      >
        Add Source
      </button>
    </div>
  );
}

function SourceRow({ source }: { source: Source }) {
  const ready = source.status === "READY";
  return (
    <Link
      href={`/app/sources/${source.id}`}
      className="rounded-xl p-4 flex items-center gap-4 transition-all hover:opacity-90"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <div className="w-12 h-12 rounded-lg flex items-center justify-center shrink-0" style={{ background: "var(--bg-secondary)" }}>
        {ready ? <Search size={18} style={{ color: "var(--accent)" }} /> : <FileText size={18} style={{ color: "var(--text-muted)" }} />}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="font-medium text-sm truncate">{source.title || "Untitled source"}</h3>
        <div className="flex flex-wrap items-center gap-3 mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          {source.creator_name && <span>{source.creator_name}</span>}
          {source.duration_sec && (
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {formatDuration(source.duration_sec)}
            </span>
          )}
          <span>{source.source_type}</span>
        </div>
      </div>
      <span
        className="px-2.5 py-1 rounded-full text-xs font-medium"
        style={{
          background: ready ? "rgba(52,199,89,0.12)" : "rgba(60,60,67,0.08)",
          color: ready ? "var(--accent-strong)" : "var(--text-secondary)",
        }}
      >
        {source.status}
      </span>
    </Link>
  );
}

function formatDuration(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes || 1}m`;
}

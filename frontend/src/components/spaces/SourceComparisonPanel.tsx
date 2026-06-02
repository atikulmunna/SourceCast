"use client";

import { FormEvent, useState } from "react";
import { Clock, ExternalLink, GitCompareArrows, Loader2 } from "lucide-react";
import api from "@/lib/api";
import { ComparisonResponse, EvidenceHit, Source, getErrorMessage } from "@/lib/types";
import { SaveInsightButton } from "@/components/insights/SaveInsightButton";

export function SourceComparisonPanel({ sources, spaceId }: { sources: Source[]; spaceId: string }) {
  const readySources = sources.filter(
    (source) => source.status === "READY" && source.indexing_status === "INDEXED"
  );
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [topic, setTopic] = useState("");
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleSource = (sourceId: string) => {
    setSelectedIds((current) =>
      current.includes(sourceId)
        ? current.filter((id) => id !== sourceId)
        : [...current, sourceId]
    );
  };

  const compare = async (event: FormEvent) => {
    event.preventDefault();
    if (selectedIds.length < 2 || !topic.trim() || comparing) return;
    setComparing(true);
    setError(null);
    setComparison(null);
    try {
      const { data } = await api.post<ComparisonResponse>("/compare", {
        topic: topic.trim(),
        source_ids: selectedIds,
        limit_per_source: 3,
      });
      setComparison(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setComparing(false);
    }
  };

  return (
    <section className="mt-8 border-t pt-8" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center gap-2 mb-4">
        <GitCompareArrows size={17} style={{ color: "#2dd4bf" }} />
        <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          Compare Sources
        </h2>
      </div>

      <form onSubmit={compare} className="rounded-lg p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        {readySources.length < 2 ? (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Index at least two sources in this space to compare them.
          </p>
        ) : (
          <>
            <div className="grid gap-2 sm:grid-cols-2 mb-4">
              {readySources.map((source) => (
                <label
                  key={source.id}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer"
                  style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(source.id)}
                    onChange={() => toggleSource(source.id)}
                    className="accent-teal-600"
                  />
                  <span className="truncate">{source.title || "Untitled source"}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                disabled={comparing}
                placeholder="Compare what these sources say about..."
                className="min-w-0 flex-1 rounded-lg px-3 py-2 text-sm outline-none disabled:opacity-50"
                style={{
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }}
              />
              <button
                type="submit"
                disabled={selectedIds.length < 2 || !topic.trim() || comparing}
                className="px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-40"
                style={{ background: "#0d9488", color: "#fff" }}
              >
                {comparing && <Loader2 size={15} className="animate-spin" />}
                Compare
              </button>
            </div>
          </>
        )}
      </form>

      {error && <p className="text-sm mt-3" style={{ color: "#f87171" }}>{error}</p>}

      {comparison && (
        <div className="mt-4 space-y-4">
          <div className="rounded-lg p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="flex items-start gap-2">
              <p className="text-sm leading-relaxed flex-1">{comparison.answer}</p>
              <SaveInsightButton spaceId={spaceId} content={comparison.answer} title={`Comparison: ${comparison.topic}`} />
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {comparison.sources.map((source) => (
              <div key={source.source_id} className="rounded-lg p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                <h3 className="text-sm font-semibold mb-3">{source.source_title || "Untitled source"}</h3>
                {source.insufficient_evidence ? (
                  <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                    No strong evidence found for this topic.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {source.evidence.map((item) => <EvidenceRow key={item.chunk_id} item={item} spaceId={spaceId} />)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function EvidenceRow({ item, spaceId }: { item: EvidenceHit; spaceId: string }) {
  return (
    <div className="rounded-lg p-3" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between gap-2 mb-1 text-xs">
        <span className="flex items-center gap-2" style={{ color: "#2dd4bf" }}>
          <span className="flex items-center gap-1">
            <Clock size={12} />
            {formatTimestamp(Number(item.start_time_sec))} - {formatTimestamp(Number(item.end_time_sec))}
          </span>
          {item.navigation_url && (
            <a href={item.navigation_url} target="_blank" rel="noreferrer" title="Open source at timestamp" className="hover:opacity-80">
              <ExternalLink size={12} />
            </a>
          )}
        </span>
        <span style={{ color: "var(--text-muted)" }}>{item.confidence_label}</span>
      </div>
      <div className="flex items-start gap-2">
        <p className="text-xs leading-relaxed flex-1" style={{ color: "var(--text-secondary)" }}>{item.excerpt}</p>
        <SaveInsightButton spaceId={spaceId} content={item.excerpt} title={item.source_title} sourceId={item.source_id} />
      </div>
    </div>
  );
}

function formatTimestamp(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

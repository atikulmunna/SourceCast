"use client";

import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Loader2, Trash2 } from "lucide-react";
import api from "@/lib/api";
import { apiPath } from "@/lib/apiBase";
import { ResearchBrief, Source, getErrorMessage } from "@/lib/types";

export function ResearchBriefsPanel({ spaceId, sources }: { spaceId: string; sources: Source[] }) {
  const queryClient = useQueryClient();
  const readySources = sources.filter(
    (source) => source.status === "READY" && source.indexing_status === "INDEXED"
  );
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeBrief, setActiveBrief] = useState<ResearchBrief | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: briefs = [], isLoading } = useQuery<ResearchBrief[]>({
    queryKey: ["briefs", spaceId],
    queryFn: async () => {
      const { data } = await api.get<ResearchBrief[]>("/briefs", { params: { space_id: spaceId } });
      return data;
    },
  });

  const toggleSource = (sourceId: string) => {
    setSelectedIds((current) =>
      current.includes(sourceId)
        ? current.filter((id) => id !== sourceId)
        : [...current, sourceId]
    );
  };

  const createBrief = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || generating) return;
    setGenerating(true);
    setError(null);
    try {
      const { data } = await api.post<ResearchBrief>("/briefs", {
        space_id: spaceId,
        title: title.trim(),
        topic: topic.trim() || null,
        source_ids: selectedIds,
      });
      setActiveBrief(data);
      setTitle("");
      setTopic("");
      await queryClient.invalidateQueries({ queryKey: ["briefs", spaceId] });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const remove = async (briefId: string) => {
    await api.delete(`/briefs/${briefId}`);
    if (activeBrief?.id === briefId) setActiveBrief(null);
    await queryClient.invalidateQueries({ queryKey: ["briefs", spaceId] });
  };

  const exportMarkdown = (briefId: string) => {
    window.open(apiPath(`/api/v1/briefs/${briefId}/export/markdown`), "_blank", "noreferrer");
  };

  return (
    <section className="mt-8 border-t pt-8" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center gap-2 mb-4">
        <FileText size={17} style={{ color: "var(--accent)" }} />
        <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          Research Briefs
        </h2>
      </div>

      <form onSubmit={createBrief} className="rounded-lg p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <div className="grid gap-3 sm:grid-cols-2 mb-3">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={generating}
            placeholder="Brief title"
            className="rounded-lg px-3 py-2 text-sm outline-none disabled:opacity-50"
            style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
          <input
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            disabled={generating}
            placeholder="Topic or research question"
            className="rounded-lg px-3 py-2 text-sm outline-none disabled:opacity-50"
            style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </div>

        {readySources.length > 0 && (
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
        )}

        <button
          type="submit"
          disabled={!title.trim() || generating}
          className="px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-40"
          style={{ background: "var(--accent)", color: "#fff" }}
        >
          {generating && <Loader2 size={15} className="animate-spin" />}
          Generate Markdown
        </button>
      </form>

      {error && <p className="text-sm mt-3" style={{ color: "var(--accent-rose)" }}>{error}</p>}

      <div className="mt-4 grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-2">
          {isLoading ? (
            <Loader2 size={16} className="animate-spin" style={{ color: "var(--accent)" }} />
          ) : briefs.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Generated Markdown briefs will appear here.
            </p>
          ) : (
            briefs.map((brief) => (
              <div key={brief.id} className="rounded-lg p-3" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                <button type="button" onClick={() => setActiveBrief(brief)} className="text-left text-sm font-medium hover:opacity-80">
                  {brief.title}
                </button>
                <div className="flex items-center gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => exportMarkdown(brief.id)}
                    title="Download Markdown"
                    className="w-8 h-8 rounded-lg flex items-center justify-center hover:opacity-80"
                    style={{ border: "1px solid var(--border)", color: "var(--accent)" }}
                  >
                    <Download size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(brief.id)}
                    title="Delete brief"
                    className="w-8 h-8 rounded-lg flex items-center justify-center hover:opacity-80"
                    style={{ border: "1px solid var(--border)", color: "var(--accent-rose)" }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="rounded-lg p-4 min-h-48 overflow-auto" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          {activeBrief?.content_markdown ? (
            <pre className="text-xs leading-relaxed whitespace-pre-wrap font-sans" style={{ color: "var(--text-secondary)" }}>
              {activeBrief.content_markdown}
            </pre>
          ) : (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Select or generate a brief to preview its Markdown.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

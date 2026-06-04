"use client";

import { FormEvent, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, ExternalLink, Loader2, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import api from "@/lib/api";
import {
  AskQuestionResponse,
  Source,
  TranscriptPage,
  TranscriptSegment,
  getErrorMessage,
} from "@/lib/types";

export default function SourceDetailPage() {
  const { sourceId } = useParams<{ sourceId: string }>();
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskQuestionResponse | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const { data: source, isLoading: sourceLoading } = useQuery<Source>({
    queryKey: ["sources", sourceId],
    queryFn: async () => {
      const { data } = await api.get<Source>(`/sources/${sourceId}`);
      return data;
    },
  });

  const { data: transcript, isLoading: transcriptLoading } = useQuery<TranscriptPage>({
    queryKey: ["transcript", sourceId, page],
    queryFn: async () => {
      const { data } = await api.get<TranscriptPage>(`/sources/${sourceId}/transcript`, {
        params: { page, limit: 50 },
      });
      return data;
    },
    enabled: source?.transcript_status === "TRANSCRIBED",
  });

  const ask = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setAskError(null);
    setAnswer(null);
    try {
      const { data } = await api.post<AskQuestionResponse>("/qa/ask", {
        question: question.trim(),
        source_ids: [sourceId],
        limit: 5,
      });
      setAnswer(data);
    } catch (err) {
      setAskError(getErrorMessage(err));
    } finally {
      setAsking(false);
    }
  };

  const deleteSource = async () => {
    if (!confirm("Delete this source and its transcript evidence? This cannot be undone.")) {
      return;
    }
    setDeleting(true);
    try {
      await api.delete(`/sources/${sourceId}`);
      router.push("/app");
    } catch (err) {
      setAskError(getErrorMessage(err));
      setDeleting(false);
    }
  };

  if (sourceLoading || !source) {
    return (
      <div className="min-h-full flex items-center justify-center">
        <Loader2 size={24} className="animate-spin" style={{ color: "var(--accent)" }} />
      </div>
    );
  }

  const ready = source.status === "READY" && source.indexing_status === "INDEXED";

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <Link
        href="/app"
        className="inline-flex items-center gap-2 text-sm mb-6"
        style={{ color: "var(--text-muted)" }}
      >
        <ArrowLeft size={15} />
        Back to workspace
      </Link>

      <header className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold truncate">{source.title || "Untitled source"}</h1>
            <div className="flex flex-wrap gap-3 mt-2 text-sm" style={{ color: "var(--text-muted)" }}>
              {source.creator_name && <span>{source.creator_name}</span>}
              {source.duration_sec && (
                <span className="flex items-center gap-1">
                  <Clock size={14} />
                  {formatDuration(source.duration_sec)}
                </span>
              )}
              <a
                href={source.canonical_url || source.source_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 hover:opacity-80"
              >
                Source <ExternalLink size={13} />
              </a>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span
              className="px-3 py-1.5 rounded-full text-xs font-medium"
              style={{
                background: ready ? "rgba(143,185,168,0.12)" : "rgba(161,161,181,0.08)",
                color: ready ? "var(--accent-strong)" : "var(--text-secondary)",
              }}
            >
              {source.status}
            </span>
            <button
              onClick={deleteSource}
              disabled={deleting}
              title="Delete source"
              className="w-8 h-8 rounded-lg flex items-center justify-center disabled:opacity-40"
              style={{ border: "1px solid var(--border)", color: "#f87171" }}
            >
              {deleting ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
            </button>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
        <section className="rounded-xl overflow-hidden" style={panelStyle}>
          <div className="p-4 border-b" style={{ borderColor: "var(--border)" }}>
            <h2 className="font-semibold">Transcript</h2>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Timestamped transcript segments from the ingestion pipeline.
            </p>
          </div>

          {source.transcript_status !== "TRANSCRIBED" ? (
            <div className="p-8 text-sm" style={{ color: "var(--text-muted)" }}>
              Transcript is not ready yet. Current status: {source.transcript_status}
            </div>
          ) : transcriptLoading ? (
            <div className="p-8 flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)" }}>
              <Loader2 size={16} className="animate-spin" />
              Loading transcript
            </div>
          ) : (
            <>
              <div className="divide-y" style={{ borderColor: "var(--border)" }}>
                {(transcript?.segments || []).map((segment) => (
                  <TranscriptRow key={segment.id} segment={segment} />
                ))}
              </div>
              <div className="p-4 flex items-center justify-between border-t" style={{ borderColor: "var(--border)" }}>
                <button
                  disabled={page === 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  className="px-3 py-1.5 rounded-lg text-sm disabled:opacity-40"
                  style={{ border: "1px solid var(--border)" }}
                >
                  Previous
                </button>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Page {page}
                </span>
                <button
                  disabled={!transcript?.has_more}
                  onClick={() => setPage((value) => value + 1)}
                  className="px-3 py-1.5 rounded-lg text-sm disabled:opacity-40"
                  style={{ border: "1px solid var(--border)" }}
                >
                  Next
                </button>
              </div>
            </>
          )}
        </section>

        <aside className="rounded-xl p-4 sticky top-6" style={panelStyle}>
          <div className="flex items-center gap-2 mb-3">
            <Search size={17} style={{ color: "var(--accent)" }} />
            <h2 className="font-semibold">Ask This Source</h2>
          </div>
          <form onSubmit={ask} className="space-y-3">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={4}
              disabled={!ready || asking}
              placeholder={ready ? "What does this source say about..." : "Source must finish indexing first"}
              className="w-full rounded-lg p-3 text-sm outline-none resize-none disabled:opacity-50"
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            />
            <button
              disabled={!ready || asking || !question.trim()}
              className="primary-button w-full disabled:opacity-40"
            >
              {asking && <Loader2 size={15} className="animate-spin" />}
              Ask with evidence
            </button>
          </form>

          {askError && (
            <p className="text-sm mt-4" style={{ color: "#f87171" }}>
              {askError}
            </p>
          )}

          {answer && (
            <div className="mt-5 space-y-4">
              <p className="text-sm leading-relaxed">{answer.answer}</p>
              <div className="space-y-3">
                {answer.evidence.map((item) => (
                  <div key={item.chunk_id} className="rounded-lg p-3" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium" style={{ color: "var(--accent-strong)" }}>
                          {formatTimestamp(Number(item.start_time_sec))} - {formatTimestamp(Number(item.end_time_sec))}
                        </span>
                        {item.navigation_url && (
                          <a
                            href={item.navigation_url}
                            target="_blank"
                            rel="noreferrer"
                            title="Open source at timestamp"
                            className="hover:opacity-80"
                            style={{ color: "var(--accent-strong)" }}
                          >
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {item.confidence_label}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                      {item.excerpt}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function TranscriptRow({ segment }: { segment: TranscriptSegment }) {
  return (
    <div className="grid grid-cols-[84px_minmax(0,1fr)] gap-4 p-4">
      <span className="text-xs font-medium" style={{ color: "var(--accent-strong)" }}>
        {formatTimestamp(Number(segment.start_time_sec))}
      </span>
      <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {segment.text}
      </p>
    </div>
  );
}

function formatTimestamp(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function formatDuration(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes || 1}m`;
}

const panelStyle = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
};

"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, RotateCcw } from "lucide-react";
import api from "@/lib/api";
import { Job } from "@/lib/types";

const TERMINAL = new Set(["COMPLETED", "FAILED", "STALE", "CANCELLED"]);

interface Props {
  jobId: string;
  onDone?: () => void;
}

export function JobProgressPanel({ jobId, onDone }: Props) {
  // Polling is the single source of job progress. Ingestion takes minutes, so a
  // 3 second refresh is enough, and polling stops once the job is terminal.
  const { data: job, refetch } = useQuery<Job>({
    queryKey: ["jobs", jobId],
    queryFn: async () => {
      const { data } = await api.get<Job>(`/jobs/${jobId}`);
      return data;
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL.has(status) ? false : 3000;
    },
  });

  useEffect(() => {
    if (job?.status === "COMPLETED") onDone?.();
  }, [job?.status, onDone]);

  const retry = async () => {
    await api.post(`/jobs/${jobId}/retry`);
    // The job is QUEUED again, which restarts polling.
    refetch();
  };

  if (!job) {
    return (
      <div className="rounded-lg p-4 flex items-center gap-3" style={panelStyle}>
        <Loader2 size={16} className="animate-spin" />
        <span className="text-sm">Loading job status</span>
      </div>
    );
  }

  const failed = job.status === "FAILED" || job.status === "STALE";
  const completed = job.status === "COMPLETED";

  return (
    <div className="rounded-lg p-4 space-y-3" style={panelStyle}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {completed ? (
            <CheckCircle2 size={17} style={{ color: "var(--accent-emerald)" }} />
          ) : failed ? (
            <AlertTriangle size={17} style={{ color: "var(--accent-rose)" }} />
          ) : (
            <Loader2 size={17} className="animate-spin" style={{ color: "var(--accent)" }} />
          )}
          <div>
            <p className="text-sm font-medium">{job.status.replaceAll("_", " ")}</p>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              {job.current_step || job.stage || "Preparing source"}
            </p>
          </div>
        </div>
        {job.is_retryable && (
          <button
            onClick={retry}
            className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5"
            style={{
              border: "1px solid var(--border)",
              color: "var(--text-secondary)",
            }}
          >
            <RotateCcw size={13} />
            Retry
          </button>
        )}
      </div>

      <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-primary)" }}>
        <div
          className="h-full transition-all"
          style={{
            width: `${Math.max(0, Math.min(100, job.progress))}%`,
            background: failed ? "var(--accent-rose)" : "var(--accent)",
          }}
        />
      </div>

      {job.error_message && (
        <p className="text-xs" style={{ color: "var(--accent-rose)" }}>
          {job.error_message}
        </p>
      )}
    </div>
  );
}

const panelStyle = {
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
};

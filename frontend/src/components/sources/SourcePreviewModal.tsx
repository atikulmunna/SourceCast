"use client";

import { useState } from "react";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Link2,
  Loader2,
  AlertTriangle,
  Clock,
  User,
  Calendar,
  Info,
  Play,
} from "lucide-react";
import api from "@/lib/api";
import {
  SourceIngestResponse,
  SourcePreview,
  getErrorMessage,
} from "@/lib/types";

interface Props {
  open: boolean;
  onClose: () => void;
  spaceId?: string;
  onIngested?: (result: SourceIngestResponse) => void;
}

export function SourcePreviewModal({
  open,
  onClose,
  spaceId,
  onIngested,
}: Props) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [preview, setPreview] = useState<SourcePreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    setPreview(null);
    try {
      const { data } = await api.post<SourcePreview>("/sources/preview", {
        url: url.trim(),
      });
      setPreview(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleIngest = async () => {
    if (!preview || !spaceId) {
      setError("Open a knowledge space before starting ingestion.");
      return;
    }
    setIngesting(true);
    setError(null);
    try {
      const { data } = await api.post<SourceIngestResponse>("/sources", {
        url: preview.url,
        space_id: spaceId,
      });
      onIngested?.(data);
      handleClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIngesting(false);
    }
  };

  const handleClose = () => {
    setUrl("");
    setPreview(null);
    setError(null);
    setIngesting(false);
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 z-40"
            style={{
              background: "rgba(0,0,0,0.65)",
              backdropFilter: "blur(4px)",
            }}
          />

          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 16 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              className="surface w-full max-w-lg p-6"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h2 className="font-semibold">Add Source</h2>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    Paste a YouTube, podcast, or audio URL
                  </p>
                </div>
                <button
                  onClick={handleClose}
                  style={{ color: "var(--text-muted)" }}
                >
                  <X size={18} />
                </button>
              </div>

              {/* URL Input */}
              <div className="flex gap-2 mb-4">
                <div className="relative flex-1">
                  <Link2
                    size={15}
                    className="absolute left-3 top-1/2 -translate-y-1/2"
                    style={{ color: "var(--text-muted)" }}
                  />
                  <input
                    id="source-url-input"
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handlePreview()}
                    placeholder="https://youtube.com/watch?v=..."
                    className="w-full pl-9 pr-4 py-2.5 rounded-md text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                  />
                </div>
                <button
                  id="preview-url-btn"
                  onClick={handlePreview}
                  disabled={loading || !url.trim()}
                  className="primary-button disabled:opacity-40"
                >
                  {loading ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    "Preview"
                  )}
                </button>
              </div>

              {/* Error */}
              {error && (
                <div
                  className="p-3 rounded-lg text-sm mb-4 flex items-start gap-2"
                  style={{
                    background: "rgba(225,29,72,0.08)",
                    border: "1px solid rgba(225,29,72,0.2)",
                    color: "var(--accent-rose)",
                  }}
                >
                  <AlertTriangle size={15} className="shrink-0 mt-0.5" />
                  {error}
                </div>
              )}

              {/* Preview card */}
              {preview && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-lg overflow-hidden"
                  style={{ border: "1px solid var(--border)" }}
                >
                  {/* Thumbnail */}
                  {preview.thumbnail_url && (
                    <Image
                      src={preview.thumbnail_url}
                      alt={preview.title || "Source thumbnail"}
                      width={640}
                      height={352}
                      unoptimized
                      className="w-full h-44 object-cover"
                    />
                  )}

                  <div className="p-4">
                    <h3 className="font-semibold text-sm mb-2 leading-snug">
                      {preview.title || "Untitled source"}
                    </h3>

                    <div
                      className="flex flex-wrap gap-3 text-xs mb-3"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {preview.creator_name && (
                        <span className="flex items-center gap-1">
                          <User size={11} /> {preview.creator_name}
                        </span>
                      )}
                      {preview.duration_label && (
                        <span className="flex items-center gap-1">
                          <Clock size={11} /> {preview.duration_label}
                        </span>
                      )}
                      {preview.publish_date && (
                        <span className="flex items-center gap-1">
                          <Calendar size={11} />
                          {new Date(preview.publish_date).getFullYear()}
                        </span>
                      )}
                    </div>

                    {/* Processing estimate */}
                    {preview.processing_estimate && (
                      <div
                        className="rounded-lg p-3 mb-3 text-xs"
                        style={{
                          background: "var(--bg-secondary)",
                          border: "1px solid var(--border)",
                        }}
                      >
                        <div className="flex items-center gap-1.5 mb-1 font-medium">
                          <Clock size={12} />
                          Estimated processing time:{" "}
                          <span style={{ color: "var(--accent-strong)" }}>
                            {preview.processing_estimate.estimated_label}
                          </span>
                        </div>
                        <p style={{ color: "var(--text-muted)" }}>
                          Using Whisper {preview.processing_estimate.model_used}{" "}
                          on CPU
                        </p>
                      </div>
                    )}

                    {/* Long content warning */}
                    {preview.processing_estimate?.warning && (
                      <div
                        className="rounded-lg p-3 mb-3 text-xs flex items-start gap-2"
                        style={{
                          background: "rgba(217,119,6,0.08)",
                          border: "1px solid rgba(217,119,6,0.25)",
                          color: "#fbbf24",
                        }}
                      >
                        <Info size={13} className="shrink-0 mt-0.5" />
                        {preview.processing_estimate.warning}
                      </div>
                    )}

                    <button
                      id="ingest-source-btn"
                      onClick={handleIngest}
                      disabled={ingesting || !spaceId}
                      className="primary-button w-full disabled:opacity-40 disabled:cursor-not-allowed"
                      title={spaceId ? "Start ingestion" : "Open a space first"}
                    >
                      {ingesting ? (
                        <>
                          <Loader2 size={15} className="animate-spin" />
                          Starting ingestion
                        </>
                      ) : (
                        <>
                          <Play size={15} />
                          Start ingestion
                        </>
                      )}
                    </button>
                  </div>
                </motion.div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

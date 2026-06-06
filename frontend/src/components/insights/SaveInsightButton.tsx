"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BookmarkCheck, BookmarkPlus, CircleAlert, Loader2 } from "lucide-react";
import api from "@/lib/api";

interface SaveInsightButtonProps {
  spaceId: string;
  content: string;
  title?: string | null;
  sourceId?: string | null;
  evidenceItemId?: string | null;
}

export function SaveInsightButton({
  spaceId,
  content,
  title,
  sourceId,
  evidenceItemId,
}: SaveInsightButtonProps) {
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [failed, setFailed] = useState(false);

  const save = async () => {
    if (saving || saved) return;
    setSaving(true);
    setFailed(false);
    try {
      await api.post("/insights", {
        space_id: spaceId,
        source_id: sourceId || null,
        evidence_item_id: evidenceItemId || null,
        title: title || null,
        content,
      });
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: ["insights", spaceId] });
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <button
      type="button"
      onClick={save}
      disabled={saving || saved}
      title={saved ? "Saved insight" : failed ? "Save failed. Try again" : "Save insight"}
      className="w-7 h-7 shrink-0 rounded-lg flex items-center justify-center disabled:opacity-60 hover:opacity-80"
      style={{
        color: saved
          ? "var(--accent-emerald)"
          : failed
            ? "var(--accent-rose)"
            : "var(--text-muted)",
        border: "1px solid var(--border)",
      }}
    >
      {saving ? <Loader2 size={13} className="animate-spin" /> : saved ? <BookmarkCheck size={13} /> : failed ? <CircleAlert size={13} /> : <BookmarkPlus size={13} />}
    </button>
  );
}

"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Loader2, Trash2 } from "lucide-react";
import api from "@/lib/api";
import { SavedInsight } from "@/lib/types";

export function SavedInsightsPanel({ spaceId }: { spaceId: string }) {
  const queryClient = useQueryClient();
  const { data: insights = [], isLoading } = useQuery<SavedInsight[]>({
    queryKey: ["insights", spaceId],
    queryFn: async () => {
      const { data } = await api.get<SavedInsight[]>("/insights", { params: { space_id: spaceId } });
      return data;
    },
  });

  const remove = async (insightId: string) => {
    await api.delete(`/insights/${insightId}`);
    await queryClient.invalidateQueries({ queryKey: ["insights", spaceId] });
  };

  return (
    <section className="mt-8 border-t pt-8" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Bookmark size={17} style={{ color: "var(--accent)" }} />
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Saved Insights
          </h2>
        </div>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>{insights.length} saved</span>
      </div>

      {isLoading ? (
        <Loader2 size={16} className="animate-spin" style={{ color: "var(--accent)" }} />
      ) : insights.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Save useful answers or evidence cards to collect research notes here.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {insights.map((insight) => (
            <div key={insight.id} className="rounded-lg p-3" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="text-xs font-medium">{insight.title || "Saved insight"}</p>
                <button
                  type="button"
                  onClick={() => remove(insight.id)}
                  title="Delete saved insight"
                  className="w-7 h-7 shrink-0 rounded-lg flex items-center justify-center hover:opacity-80"
                  style={{ color: "var(--accent-rose)", border: "1px solid var(--border)" }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>{insight.content}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

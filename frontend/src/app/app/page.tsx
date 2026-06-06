"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Layers, Plus, BookOpen, Zap } from "lucide-react";
import api from "@/lib/api";
import { KnowledgeSpace } from "@/lib/types";
import { useAuthStore } from "@/store/authStore";
import { CreateSpaceModal } from "@/components/spaces/CreateSpaceModal";
import { SpaceCard } from "@/components/spaces/SpaceCard";
import { SourcePreviewModal } from "@/components/sources/SourcePreviewModal";

export default function AppDashboard() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [showCreateSpace, setShowCreateSpace] = useState(false);
  const [showAddSource, setShowAddSource] = useState(false);
  const [selectedSpaceId, setSelectedSpaceId] = useState<string>("");

  const {
    data: spaces = [],
    isLoading,
    refetch,
  } = useQuery<KnowledgeSpace[]>({
    queryKey: ["spaces"],
    queryFn: async () => {
      const { data } = await api.get<KnowledgeSpace[]>("/spaces");
      return data;
    },
  });

  const activeSpaceId = selectedSpaceId || spaces[0]?.id || "";

  const handleDashboardIngested = () => {
    setShowAddSource(false);
    if (activeSpaceId) {
      router.push(`/app/spaces/${activeSpaceId}`);
    }
  };

  return (
    <div className="p-6 sm:p-8 max-w-5xl mx-auto animate-fade-in">
      <div className="mb-8">
        <p className="text-sm mb-1" style={{ color: "var(--text-muted)" }}>
          Welcome back, {user?.name || user?.email?.split("@")[0]}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">Research workspace</h1>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-8">
        <button
          id="create-space-btn"
          onClick={() => setShowCreateSpace(true)}
          className="primary-button"
        >
          <Plus size={16} />
          New Space
        </button>
        <button
          id="add-source-btn"
          onClick={() => setShowAddSource(true)}
          disabled={!activeSpaceId}
          className="secondary-button"
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
          }}
        >
          <Plus size={16} />
          Add Source
        </button>
        {spaces.length > 0 && (
          <select
            value={activeSpaceId}
            onChange={(event) => setSelectedSpaceId(event.target.value)}
            className="h-10 rounded-md px-3 text-sm outline-none"
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              color: "var(--text-secondary)",
            }}
          >
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Spaces grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-36 rounded-xl skeleton"
            />
          ))}
        </div>
      ) : spaces.length === 0 ? (
        <EmptyState onCreateSpace={() => setShowCreateSpace(true)} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {spaces.map((space) => (
            <div
              key={space.id}
            >
              <SpaceCard space={space} onDeleted={refetch} />
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      <CreateSpaceModal
        open={showCreateSpace}
        onClose={() => setShowCreateSpace(false)}
        onCreated={() => {
          setShowCreateSpace(false);
          refetch();
        }}
      />
      <SourcePreviewModal
        open={showAddSource}
        onClose={() => setShowAddSource(false)}
        spaceId={activeSpaceId}
        onIngested={handleDashboardIngested}
      />
    </div>
  );
}

function EmptyState({ onCreateSpace }: { onCreateSpace: () => void }) {
  return (
    <div className="text-center py-20 animate-fade-in">
      <div
        className="inline-flex w-14 h-14 rounded-lg items-center justify-center mb-5"
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
        }}
      >
        <Layers size={24} style={{ color: "var(--accent)" }} />
      </div>
      <h2 className="text-xl font-semibold mb-2">No knowledge spaces yet</h2>
      <p
        className="text-sm mb-6 max-w-sm mx-auto"
        style={{ color: "var(--text-muted)" }}
      >
        Create a space to organize your sources, chats, and research briefs.
      </p>
      <div
        className="flex items-center justify-center gap-4 flex-wrap text-sm"
        style={{ color: "var(--text-muted)" }}
      >
        <div className="flex items-center gap-1.5">
          <BookOpen size={14} />
          Add YouTube or podcast sources
        </div>
        <div className="flex items-center gap-1.5">
          <Zap size={14} />
          Chat with timestamped evidence
        </div>
      </div>
      <button
        id="empty-create-space-btn"
        onClick={onCreateSpace}
        className="primary-button mt-6"
      >
        <Plus size={15} />
        Create your first space
      </button>
    </div>
  );
}

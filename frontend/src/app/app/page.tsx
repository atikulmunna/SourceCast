"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Layers, Plus, BookOpen, Zap } from "lucide-react";
import api from "@/lib/api";
import { KnowledgeSpace } from "@/lib/types";
import { useAuthStore } from "@/store/authStore";
import { CreateSpaceModal } from "@/components/spaces/CreateSpaceModal";
import { SpaceCard } from "@/components/spaces/SpaceCard";
import { SourcePreviewModal } from "@/components/sources/SourcePreviewModal";

export default function AppDashboard() {
  const { user } = useAuthStore();
  const [showCreateSpace, setShowCreateSpace] = useState(false);
  const [showAddSource, setShowAddSource] = useState(false);

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

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-10"
      >
        <p className="text-sm mb-1" style={{ color: "var(--text-muted)" }}>
          Welcome back, {user?.name || user?.email?.split("@")[0]}
        </p>
        <h1 className="text-3xl font-bold">Your Research Workspace</h1>
      </motion.div>

      {/* Action bar */}
      <div className="flex items-center gap-3 mb-8">
        <button
          id="create-space-btn"
          onClick={() => setShowCreateSpace(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all hover:opacity-90 active:scale-95"
          style={{
            background: "linear-gradient(135deg, #0d9488, #0891b2)",
            color: "#fff",
          }}
        >
          <Plus size={16} />
          New Space
        </button>
        <button
          id="add-source-btn"
          onClick={() => setShowAddSource(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all"
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
          }}
        >
          <Plus size={16} />
          Add Source
        </button>
      </div>

      {/* Spaces grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-36 rounded-xl animate-pulse"
              style={{ background: "var(--bg-card)" }}
            />
          ))}
        </div>
      ) : spaces.length === 0 ? (
        <EmptyState onCreateSpace={() => setShowCreateSpace(true)} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {spaces.map((space, i) => (
            <motion.div
              key={space.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.06 }}
            >
              <SpaceCard space={space} onDeleted={refetch} />
            </motion.div>
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
      />
    </div>
  );
}

function EmptyState({ onCreateSpace }: { onCreateSpace: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="text-center py-20"
    >
      <div
        className="inline-flex w-16 h-16 rounded-2xl items-center justify-center mb-5"
        style={{
          background: "rgba(13,148,136,0.08)",
          border: "1px solid rgba(13,148,136,0.2)",
        }}
      >
        <Layers size={28} style={{ color: "#2dd4bf" }} />
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
        className="mt-6 inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-medium transition-all hover:opacity-90"
        style={{
          background: "linear-gradient(135deg, #0d9488, #0891b2)",
          color: "#fff",
        }}
      >
        <Plus size={15} />
        Create your first space
      </button>
    </motion.div>
  );
}

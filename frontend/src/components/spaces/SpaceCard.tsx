"use client";

import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
import { Layers, MoreHorizontal, Trash2, ArrowRight } from "lucide-react";
import api from "@/lib/api";
import { KnowledgeSpace } from "@/lib/types";

interface Props {
  space: KnowledgeSpace;
  onDeleted: () => void;
}

export function SpaceCard({ space, onDeleted }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!confirm(`Delete space "${space.name}"? This cannot be undone.`))
      return;
    setDeleting(true);
    try {
      await api.delete(`/spaces/${space.id}`);
      onDeleted();
    } finally {
      setDeleting(false);
      setMenuOpen(false);
    }
  };

  return (
    <Link href={`/app/spaces/${space.id}`} className="block group">
      <motion.div
        whileHover={{ scale: 1.02 }}
        transition={{ duration: 0.15 }}
        className="relative rounded-xl p-5 h-36 flex flex-col justify-between cursor-pointer transition-all"
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
        }}
      >
        {/* Top row */}
        <div className="flex items-start justify-between">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center"
            style={{
              background: "rgba(13,148,136,0.1)",
              border: "1px solid rgba(13,148,136,0.15)",
            }}
          >
            <Layers size={16} style={{ color: "#2dd4bf" }} />
          </div>

          {/* Menu button */}
          <div className="relative">
            <button
              id={`space-menu-${space.id}`}
              onClick={(e) => {
                e.preventDefault();
                setMenuOpen((v) => !v);
              }}
              className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
              style={{ color: "var(--text-muted)" }}
            >
              <MoreHorizontal size={16} />
            </button>

            {menuOpen && (
              <div
                className="absolute right-0 top-8 w-40 rounded-xl py-1 z-10 shadow-xl"
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                }}
              >
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors hover:opacity-80"
                  style={{ color: "#f87171" }}
                >
                  <Trash2 size={14} />
                  {deleting ? "Deleting…" : "Delete space"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Space name and description */}
        <div>
          <h3 className="font-semibold text-sm mb-0.5 truncate">
            {space.name}
          </h3>
          {space.description ? (
            <p
              className="text-xs truncate"
              style={{ color: "var(--text-muted)" }}
            >
              {space.description}
            </p>
          ) : (
            <p
              className="text-xs flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all"
              style={{ color: "#2dd4bf" }}
            >
              Open space <ArrowRight size={11} />
            </p>
          )}
        </div>
      </motion.div>
    </Link>
  );
}

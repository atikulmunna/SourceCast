"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Layers,
  Plus,
  Settings,
  LogOut,
  ChevronRight,
  LayoutDashboard,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { KnowledgeSpace } from "@/lib/types";
import { useAuthStore } from "@/store/authStore";
import { CreateSpaceModal } from "@/components/spaces/CreateSpaceModal";

export function AppSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const [showCreateSpace, setShowCreateSpace] = useState(false);

  const { data: spaces = [], refetch } = useQuery<KnowledgeSpace[]>({
    queryKey: ["spaces"],
    queryFn: async () => {
      const { data } = await api.get<KnowledgeSpace[]>("/spaces");
      return data;
    },
  });

  const handleLogout = async () => {
    await logout();
  };

  return (
    <>
      <aside
        className="flex flex-col w-64 shrink-0 border-r"
        style={{
          background: "var(--bg-secondary)",
          borderColor: "var(--border)",
        }}
      >
        {/* Logo */}
        <div
          className="h-14 px-4 flex items-center gap-2 border-b shrink-0"
          style={{ borderColor: "var(--border)" }}
        >
          <div
            className="brand-mark"
          >
            SC
          </div>
          <span className="font-semibold text-sm">SourceCast</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {/* Dashboard link */}
          <SidebarLink
            href="/app"
            icon={<LayoutDashboard size={15} />}
            label="Dashboard"
            active={pathname === "/app"}
          />

          {/* Spaces section */}
          <div className="pt-4">
            <div className="flex items-center justify-between px-2 mb-1">
              <span
                className="text-xs font-medium uppercase tracking-wider"
                style={{ color: "var(--text-muted)" }}
              >
                Spaces
              </span>
              <button
                id="sidebar-create-space-btn"
                onClick={() => setShowCreateSpace(true)}
                className="p-1 rounded-md transition-colors hover:opacity-80"
                style={{ color: "var(--text-muted)" }}
                title="New space"
              >
                <Plus size={14} />
              </button>
            </div>

            <AnimatePresence>
              {spaces.map((space) => (
                <motion.div
                  key={space.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  <SidebarLink
                    href={`/app/spaces/${space.id}`}
                    icon={<Layers size={14} />}
                    label={space.name}
                    active={pathname === `/app/spaces/${space.id}`}
                  />
                </motion.div>
              ))}
            </AnimatePresence>

            {spaces.length === 0 && (
              <p
                className="px-3 py-2 text-xs"
                style={{ color: "var(--text-muted)" }}
              >
                No spaces yet
              </p>
            )}
          </div>
        </nav>

        {/* User footer */}
        <div
          className="border-t p-3 space-y-1 shrink-0"
          style={{ borderColor: "var(--border)" }}
        >
          <SidebarLink
            href="/app/settings"
            icon={<Settings size={15} />}
            label="Settings"
            active={pathname === "/app/settings"}
          />
          <button
            id="sidebar-logout-btn"
            onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors hover:opacity-80 text-left"
            style={{ color: "var(--text-muted)" }}
          >
            <LogOut size={15} />
            <span>Sign out</span>
          </button>
          <div
            className="px-3 py-2 text-xs truncate"
            style={{ color: "var(--text-muted)" }}
          >
            {user?.email}
          </div>
        </div>
      </aside>

      <CreateSpaceModal
        open={showCreateSpace}
        onClose={() => setShowCreateSpace(false)}
        onCreated={() => {
          setShowCreateSpace(false);
          refetch();
        }}
      />
    </>
  );
}

function SidebarLink({
  href,
  icon,
  label,
  active,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-all group"
      style={{
        background: active ? "var(--bg-card)" : "transparent",
        color: active ? "var(--text-primary)" : "var(--text-secondary)",
        border: active
          ? "1px solid var(--border)"
          : "1px solid transparent",
      }}
    >
      {icon}
      <span className="flex-1 truncate">{label}</span>
      {active && <ChevronRight size={13} style={{ color: "var(--text-muted)" }} />}
    </Link>
  );
}

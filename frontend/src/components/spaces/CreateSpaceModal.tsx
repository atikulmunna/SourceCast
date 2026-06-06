"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion, AnimatePresence } from "framer-motion";
import { X, Layers, AlertCircle } from "lucide-react";
import api from "@/lib/api";
import { getErrorMessage } from "@/lib/types";

const schema = z.object({
  name: z.string().min(1, "Space name is required").max(255),
  description: z.string().max(2000).optional(),
});
type FormData = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function CreateSpaceModal({ open, onClose, onCreated }: Props) {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await api.post("/spaces", data);
      reset();
      onCreated();
    } catch (err) {
      setError("root", { message: getErrorMessage(err) });
    }
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 z-40"
            style={{
              background: "rgba(0,0,0,0.6)",
              backdropFilter: "blur(4px)",
            }}
          />

          {/* Modal */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 16 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              className="surface w-full max-w-md p-6"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{
                      background: "var(--bg-secondary)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <Layers size={18} style={{ color: "var(--accent)" }} />
                  </div>
                  <div>
                    <h2 className="font-semibold">New Knowledge Space</h2>
                    <p
                      className="text-xs"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Organize sources, chats, and research
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleClose}
                  className="p-2 rounded-lg transition-colors hover:opacity-70"
                  style={{ color: "var(--text-muted)" }}
                >
                  <X size={18} />
                </button>
              </div>

              <form
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-4"
                noValidate
              >
                {errors.root && (
                  <div
                    className="flex items-center gap-2 p-3 rounded-lg text-sm"
                    style={{
                      background: "rgba(225,29,72,0.08)",
                      border: "1px solid rgba(225,29,72,0.2)",
                      color: "var(--accent-rose)",
                    }}
                  >
                    <AlertCircle size={15} />
                    {errors.root.message}
                  </div>
                )}

                <div>
                  <label
                    className="block text-sm font-medium mb-2"
                    htmlFor="space-name"
                  >
                    Space name
                  </label>
                  <input
                    id="space-name"
                    type="text"
                    autoFocus
                    placeholder="e.g. Board interviews, Lecture notes"
                    {...register("name")}
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={{
                      background: "var(--bg-secondary)",
                      border: `1px solid ${errors.name ? "rgba(225,29,72,0.4)" : "var(--border)"}`,
                      color: "var(--text-primary)",
                    }}
                  />
                  {errors.name && (
                    <p className="text-xs mt-1" style={{ color: "var(--accent-rose)" }}>
                      {errors.name.message}
                    </p>
                  )}
                </div>

                <div>
                  <label
                    className="block text-sm font-medium mb-2"
                    htmlFor="space-description"
                  >
                    Description{" "}
                    <span style={{ color: "var(--text-muted)" }}>
                      (optional)
                    </span>
                  </label>
                  <textarea
                    id="space-description"
                    rows={3}
                    placeholder="What is this space for?"
                    {...register("description")}
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none resize-none"
                    style={{
                      background: "var(--bg-secondary)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                  />
                </div>

                <div className="flex items-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={handleClose}
                    className="secondary-button flex-1"
                    style={{
                      border: "1px solid var(--border)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    id="create-space-submit"
                    type="submit"
                    disabled={isSubmitting}
                    className="primary-button flex-1 disabled:opacity-50"
                  >
                    {isSubmitting ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Creating…
                      </span>
                    ) : (
                      "Create space"
                    )}
                  </button>
                </div>
              </form>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

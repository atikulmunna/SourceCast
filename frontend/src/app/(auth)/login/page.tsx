"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Mail, Lock, AlertCircle, ArrowRight } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { getErrorMessage } from "@/lib/types";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuthStore();
  const router = useRouter();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await login(data.email, data.password);
      router.push("/app");
    } catch (err) {
      setError("root", { message: getErrorMessage(err) });
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: "var(--bg-primary)" }}
    >
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold"
              style={{
                background: "linear-gradient(135deg, #0d9488, #0891b2)",
              }}
            >
              SC
            </div>
            <span className="font-semibold text-xl">SourceCast</span>
          </div>
          <h1 className="text-2xl font-bold mb-1">Welcome back</h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Sign in to your research workspace
          </p>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl p-8 gradient-border"
          style={{ background: "var(--bg-card)" }}
        >
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="space-y-5"
            noValidate
          >
            {/* Global error */}
            {errors.root && (
              <div
                className="flex items-center gap-2 p-3 rounded-lg text-sm"
                style={{
                  background: "rgba(225,29,72,0.08)",
                  border: "1px solid rgba(225,29,72,0.2)",
                  color: "#f87171",
                }}
              >
                <AlertCircle size={15} />
                {errors.root.message}
              </div>
            )}

            {/* Email */}
            <div>
              <label
                className="block text-sm font-medium mb-2"
                htmlFor="login-email"
              >
                Email
              </label>
              <div className="relative">
                <Mail
                  size={16}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2"
                  style={{ color: "var(--text-muted)" }}
                />
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  {...register("email")}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm outline-none transition-all"
                  style={{
                    background: "var(--bg-secondary)",
                    border: `1px solid ${errors.email ? "rgba(225,29,72,0.4)" : "var(--border)"}`,
                    color: "var(--text-primary)",
                  }}
                />
              </div>
              {errors.email && (
                <p className="text-xs mt-1" style={{ color: "#f87171" }}>
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                className="block text-sm font-medium mb-2"
                htmlFor="login-password"
              >
                Password
              </label>
              <div className="relative">
                <Lock
                  size={16}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2"
                  style={{ color: "var(--text-muted)" }}
                />
                <input
                  id="login-password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  {...register("password")}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm outline-none transition-all"
                  style={{
                    background: "var(--bg-secondary)",
                    border: `1px solid ${errors.password ? "rgba(225,29,72,0.4)" : "var(--border)"}`,
                    color: "var(--text-primary)",
                  }}
                />
              </div>
              {errors.password && (
                <p className="text-xs mt-1" style={{ color: "#f87171" }}>
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              id="login-submit"
              type="submit"
              disabled={isSubmitting}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm transition-all hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: "linear-gradient(135deg, #0d9488, #0891b2)",
                color: "#fff",
              }}
            >
              {isSubmitting ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  Sign in <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
        </div>

        <p
          className="text-center text-sm mt-6"
          style={{ color: "var(--text-muted)" }}
        >
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-medium transition-colors hover:opacity-80"
            style={{ color: "#2dd4bf" }}
          >
            Create one free
          </Link>
        </p>
      </motion.div>
    </div>
  );
}

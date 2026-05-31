"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Search,
  Clock,
  BookOpen,
  BarChart3,
  Layers,
  FileText,
  ArrowRight,
  CheckCircle2,
  Zap,
} from "lucide-react";

const features = [
  {
    icon: Search,
    title: "Evidence-Based Answers",
    desc: "Every answer is grounded in timestamped transcript evidence. No hallucinations, no guessing.",
  },
  {
    icon: Clock,
    title: "Timestamp Citations",
    desc: "Click any citation to jump to the exact source moment on YouTube or your audio file.",
  },
  {
    icon: Layers,
    title: "Knowledge Spaces",
    desc: "Organize sources into research workspaces. Chat, compare, and export across any scope.",
  },
  {
    icon: BarChart3,
    title: "Comparison Mode",
    desc: "Ask what multiple sources say about a topic. See agreements, differences, and tensions.",
  },
  {
    icon: BookOpen,
    title: "Claim Explorer",
    desc: "Auto-extracted key claims from every source, each linked back to timestamped evidence.",
  },
  {
    icon: FileText,
    title: "Research Briefs",
    desc: "Generate exportable Markdown research reports with evidence tables and source lists.",
  },
];

const differentiators = [
  "Answers only when evidence exists",
  "Clickable timestamp citations",
  "Cross-source comparison",
  "Normalized evidence panel per answer",
  "No-evidence refusal behavior",
  "Markdown research brief export",
];

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

export default function LandingPage() {
  return (
    <div
      className="min-h-screen"
      style={{ background: "var(--bg-primary)", color: "var(--text-primary)" }}
    >
      {/* ── Nav ─────────────────────────────────────────────────────────────── */}
      <nav
        className="fixed top-0 inset-x-0 z-50 glass"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
              style={{
                background: "linear-gradient(135deg, #0d9488, #0891b2)",
              }}
            >
              SC
            </div>
            <span className="font-semibold text-lg">SourceCast</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="px-4 py-2 text-sm rounded-lg transition-colors"
              style={{ color: "var(--text-secondary)" }}
            >
              Sign in
            </Link>
            <Link
              href="/register"
              id="cta-nav-register"
              className="px-4 py-2 text-sm font-medium rounded-lg transition-all hover:opacity-90 active:scale-95"
              style={{
                background: "linear-gradient(135deg, #0d9488, #0891b2)",
                color: "#fff",
              }}
            >
              Get started free
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="pt-40 pb-24 px-6 text-center relative overflow-hidden">
        {/* Background glow */}
        <div
          className="absolute top-20 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full blur-3xl pointer-events-none"
          style={{
            background:
              "radial-gradient(circle, rgba(13,148,136,0.12) 0%, transparent 70%)",
          }}
        />

        <motion.div {...fadeUp} className="relative max-w-4xl mx-auto">
          <div
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium mb-8"
            style={{
              background: "rgba(13,148,136,0.12)",
              border: "1px solid rgba(13,148,136,0.3)",
              color: "#2dd4bf",
            }}
          >
            <Zap size={12} />
            Evidence-first research assistant
          </div>

          <h1 className="text-5xl sm:text-6xl font-bold leading-tight mb-6">
            Ask long-form audio{" "}
            <span className="gradient-text">and video questions.</span>
            <br />
            Get answers with{" "}
            <span className="gradient-text">exact source evidence.</span>
          </h1>

          <p
            className="text-lg max-w-2xl mx-auto mb-10 leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            SourceCast transforms podcasts, YouTube lectures, and interviews
            into a searchable, timestamp-cited research knowledge base. Every
            answer traces back to the exact source moment.
          </p>

          <div className="flex items-center justify-center gap-4 flex-wrap">
            <Link
              href="/register"
              id="cta-hero-register"
              className="group inline-flex items-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-base transition-all hover:opacity-90 active:scale-95"
              style={{
                background: "linear-gradient(135deg, #0d9488, #0891b2)",
                color: "#fff",
                boxShadow: "0 0 40px rgba(13,148,136,0.3)",
              }}
            >
              Start for free
              <ArrowRight
                size={18}
                className="group-hover:translate-x-1 transition-transform"
              />
            </Link>
            <Link
              href="/login"
              className="px-8 py-3.5 rounded-xl font-medium text-base transition-all"
              style={{
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
              }}
            >
              Sign in
            </Link>
          </div>
        </motion.div>
      </section>

      {/* ── Evidence panel preview ──────────────────────────────────────────── */}
      <section className="py-16 px-6">
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="max-w-3xl mx-auto"
        >
          <div
            className="rounded-2xl p-6 gradient-border"
            style={{ background: "var(--bg-card)" }}
          >
            <div
              className="text-xs font-medium mb-4 flex items-center gap-2"
              style={{ color: "var(--text-muted)" }}
            >
              <div
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ background: "#059669" }}
              />
              Evidence Panel — Confidence: High
            </div>
            <p
              className="mb-4 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                Q: What does Andrew Huberman say about dopamine and motivation?
              </span>
            </p>
            <p className="text-sm leading-relaxed mb-5">
              Huberman explains that dopamine is primarily a molecule of
              motivation and pursuit rather than pleasure. It is released in
              anticipation of reward, not the reward itself.{" "}
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs cursor-pointer hover:opacity-80 transition-opacity"
                style={{
                  background: "rgba(13,148,136,0.15)",
                  color: "#2dd4bf",
                  border: "1px solid rgba(13,148,136,0.3)",
                }}
              >
                <Clock size={10} />
                Huberman Lab #67 @ 23:14
              </span>
            </p>
            <div
              className="rounded-lg p-4"
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <div className="flex items-start gap-3">
                <div
                  className="text-xs px-2 py-1 rounded font-medium shrink-0"
                  style={{
                    background: "rgba(5,150,105,0.15)",
                    color: "#10b981",
                  }}
                >
                  High
                </div>
                <div>
                  <p className="text-xs font-medium mb-1">
                    Huberman Lab Episode #67
                  </p>
                  <p
                    className="text-xs mb-2"
                    style={{ color: "var(--text-muted)" }}
                  >
                    23:14 – 24:02
                  </p>
                  <p
                    className="text-xs italic"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    &quot;Dopamine is not about the reward itself — it&apos;s about the
                    pursuit. It&apos;s released in anticipation of getting something
                    you want...&quot;
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ── Features ────────────────────────────────────────────────────────── */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center mb-14"
          >
            <h2 className="text-3xl font-bold mb-4">
              Built for serious research
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              Not just another podcast chatbot.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: i * 0.07 }}
                viewport={{ once: true }}
                className="rounded-xl p-6 transition-all hover:scale-[1.02]"
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                }}
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center mb-4"
                  style={{
                    background: "rgba(13,148,136,0.12)",
                    border: "1px solid rgba(13,148,136,0.2)",
                  }}
                >
                  <f.icon size={18} style={{ color: "#2dd4bf" }} />
                </div>
                <h3 className="font-semibold mb-2">{f.title}</h3>
                <p
                  className="text-sm leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {f.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Differentiators ─────────────────────────────────────────────────── */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="rounded-2xl p-10 text-center"
            style={{
              background:
                "linear-gradient(135deg, rgba(13,148,136,0.08), rgba(8,145,178,0.05))",
              border: "1px solid rgba(13,148,136,0.2)",
            }}
          >
            <h2 className="text-2xl font-bold mb-2">Why SourceCast?</h2>
            <p
              className="text-sm mb-8"
              style={{ color: "var(--text-secondary)" }}
            >
              Evidence-first. Source-grounded. Research-grade.
            </p>
            <div className="grid sm:grid-cols-2 gap-3 text-left max-w-2xl mx-auto">
              {differentiators.map((d) => (
                <div key={d} className="flex items-center gap-3 text-sm">
                  <CheckCircle2
                    size={16}
                    style={{ color: "#2dd4bf", flexShrink: 0 }}
                  />
                  <span style={{ color: "var(--text-secondary)" }}>{d}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          viewport={{ once: true }}
        >
          <h2 className="text-3xl font-bold mb-4">
            Ready to research smarter?
          </h2>
          <p
            className="mb-8 max-w-md mx-auto"
            style={{ color: "var(--text-secondary)" }}
          >
            Add a YouTube video or podcast. Ask a question. Get an answer with
            timestamped evidence in seconds.
          </p>
          <Link
            href="/register"
            id="cta-bottom-register"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-base transition-all hover:opacity-90 active:scale-95"
            style={{
              background: "linear-gradient(135deg, #0d9488, #0891b2)",
              color: "#fff",
              boxShadow: "0 0 40px rgba(13,148,136,0.3)",
            }}
          >
            Start for free <ArrowRight size={18} />
          </Link>
        </motion.div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer
        className="py-8 px-6 text-center text-xs"
        style={{
          borderTop: "1px solid var(--border)",
          color: "var(--text-muted)",
        }}
      >
        © 2026 SourceCast. Built for research, not redistribution.
      </footer>
    </div>
  );
}

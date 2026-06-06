import Link from "next/link";
import {
  ArrowRight,
  Check,
  Clock,
  FileText,
  Layers,
  MessageSquareText,
  Search,
} from "lucide-react";

const capabilities = [
  {
    icon: Search,
    title: "Search long-form sources",
    desc: "Bring podcasts, lectures, interviews, and video notes into one private workspace.",
  },
  {
    icon: MessageSquareText,
    title: "Ask grounded questions",
    desc: "Answers stay tied to retrieved transcript passages instead of loose summaries.",
  },
  {
    icon: Clock,
    title: "Open exact moments",
    desc: "Timestamp citations point back to the source segment that supports the claim.",
  },
  {
    icon: FileText,
    title: "Export research briefs",
    desc: "Turn saved findings into Markdown reports with sources and evidence intact.",
  },
];

const checks = [
  "Private knowledge spaces",
  "Source-level and space-level chat",
  "Cross-source comparison",
  "Saved insights",
  "Markdown export",
  "Evidence-first refusals",
];

export default function LandingPage() {
  return (
    <main
      className="min-h-screen"
      style={{ background: "var(--bg-primary)", color: "var(--text-primary)" }}
    >
      <header
        className="border-b"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
      >
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Link href="/" className="flex items-center gap-3">
            <span className="brand-mark" aria-hidden="true" />
            <span className="text-sm font-semibold">SourceCast</span>
          </Link>
          <nav className="flex items-center gap-2" aria-label="Primary navigation">
            <Link
              href="/login"
              className="secondary-button h-9 px-3"
              style={{ color: "var(--text-secondary)" }}
            >
              Sign in
            </Link>
            <Link href="/register" id="cta-nav-register" className="primary-button h-9 px-4">
              Start
            </Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto grid min-h-[calc(100vh-64px)] max-w-6xl gap-10 px-5 py-12 sm:py-16 lg:grid-cols-[minmax(0,1fr)_440px] lg:items-center">
        <div className="max-w-2xl">
          <p className="mb-4 text-sm font-medium" style={{ color: "var(--text-muted)" }}>
            Research workspace for source-grounded audio and video notes
          </p>
          <h1 className="max-w-[11ch] text-5xl font-semibold leading-[1.04] tracking-tight sm:text-6xl">
            Find the part that proves the point.
          </h1>
          <p
            className="mt-6 max-w-xl text-lg leading-8"
            style={{ color: "var(--text-secondary)" }}
          >
            SourceCast turns long-form media into timestamped transcripts, searchable evidence,
            cited answers, comparisons, saved insights, and exportable research briefs.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/register"
              id="cta-hero-register"
              className="primary-button h-11 whitespace-nowrap px-5"
            >
              <span>Create workspace</span>
              <ArrowRight size={15} />
            </Link>
            <Link href="/login" className="secondary-button h-11 whitespace-nowrap px-5">
              Sign in
            </Link>
          </div>
        </div>

        <aside className="surface p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between border-b pb-4" style={{ borderColor: "var(--border)" }}>
            <div>
              <p className="text-sm font-medium">Evidence answer</p>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Source-level question
              </p>
            </div>
            <span className="rounded px-2 py-1 text-xs whitespace-nowrap" style={{ background: "var(--bg-secondary)", color: "var(--text-muted)" }}>
              High confidence
            </span>
          </div>

          <p className="text-sm leading-6" style={{ color: "var(--text-secondary)" }}>
            The speaker frames dopamine as a signal for pursuit and motivation, not simply a
            reward chemical. The strongest support appears in two transcript segments.
          </p>

          <div className="mt-5 grid gap-3">
            <EvidenceLine time="12:42" text="Dopamine rises while the goal is being pursued." />
            <EvidenceLine time="14:08" text="The reward itself can reset the next pursuit cycle." />
          </div>

          <div className="mt-5 rounded-md border p-3" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
            <p className="mb-2 text-xs font-medium" style={{ color: "var(--text-muted)" }}>
              Brief note
            </p>
            <p className="text-sm leading-6">
              Motivation depends on anticipation, progress, and recovery between peaks.
            </p>
          </div>
        </aside>
      </section>

      <section className="border-y" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <div className="mx-auto grid max-w-6xl gap-px px-5 py-10 sm:grid-cols-2 lg:grid-cols-4">
          {capabilities.map((item) => (
            <div key={item.title} className="py-5 sm:px-5">
              <item.icon size={18} className="mb-4" style={{ color: "var(--accent)" }} />
              <h2 className="mb-2 text-sm font-semibold">{item.title}</h2>
              <p className="text-sm leading-6" style={{ color: "var(--text-muted)" }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-8 px-5 py-14 md:grid-cols-[320px_minmax(0,1fr)]">
        <div>
          <Layers size={20} className="mb-4" style={{ color: "var(--accent)" }} />
          <h2 className="text-2xl font-semibold">Built around the research loop.</h2>
          <p className="mt-4 text-sm leading-6" style={{ color: "var(--text-secondary)" }}>
            The product is deliberately narrow: collect source material, inspect evidence, save
            useful findings, and export a brief when the argument is ready.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {checks.map((check) => (
            <div key={check} className="flex items-center gap-3 text-sm">
              <Check size={15} style={{ color: "var(--accent)" }} />
              <span style={{ color: "var(--text-secondary)" }}>{check}</span>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t px-5 py-8 text-center text-xs" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
        SourceCast. Built for private research workflows.
      </footer>
    </main>
  );
}

function EvidenceLine({ time, text }: { time: string; text: string }) {
  return (
    <div className="flex gap-3 rounded-md border p-3" style={{ borderColor: "var(--border)" }}>
      <span className="shrink-0 text-xs font-medium" style={{ color: "var(--accent)" }}>
        {time}
      </span>
      <p className="text-sm leading-5" style={{ color: "var(--text-secondary)" }}>
        {text}
      </p>
    </div>
  );
}

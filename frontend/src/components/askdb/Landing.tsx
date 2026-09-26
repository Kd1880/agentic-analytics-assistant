import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Sparkles, Wand2 } from "lucide-react";
import { databases, type DbId, type DatabaseConfig } from "@/lib/databases";

/** Database picker. Each card previews its own world's palette. */
export function Landing({
  onPick,
  mode = "dark",
  meta,
}: {
  onPick: (id: DbId) => void;
  mode?: "light" | "dark";
  meta?: Record<string, { tables?: number; rows?: number | string }>;
}) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 pt-16 pb-24 sm:px-6 sm:pt-24">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="mx-auto max-w-3xl text-center"
      >
        <span
          className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium"
          style={{ borderColor: "var(--line)", background: "var(--surface)", color: "var(--muted)" }}
        >
          <Sparkles className="size-3.5" style={{ color: "var(--accent)" }} />
          AskDB — Agentic Analytics Assistant
        </span>
        <h1
          className="mt-6 text-5xl leading-[1.05] font-bold tracking-tight sm:text-7xl"
          style={{ color: "var(--text)", fontFamily: "var(--display)" }}
        >
          Talk to your data.
        </h1>
        <p
          className="mx-auto mt-5 max-w-xl text-base leading-relaxed sm:text-lg"
          style={{ color: "var(--muted)" }}
        >
          AskDB turns plain English into SQL, runs it against your database, and explains the
          answer — with self-correction when a query fails and SELECT-only safety guardrails on
          every run.
        </p>
        <div
          className="mt-6 flex flex-wrap justify-center gap-2 text-xs"
          style={{ color: "var(--muted)" }}
        >
          <span
            className="flex items-center gap-1.5 rounded-full border px-3 py-1.5"
            style={{ borderColor: "var(--line)" }}
          >
            <ShieldCheck className="size-3.5" /> SELECT-only guardrails
          </span>
          <span
            className="flex items-center gap-1.5 rounded-full border px-3 py-1.5"
            style={{ borderColor: "var(--line)" }}
          >
            <Wand2 className="size-3.5" /> Self-correcting agent
          </span>
        </div>
      </motion.div>

      <div className="mt-16 grid gap-5 md:grid-cols-3">
        {databases.map((base: DatabaseConfig, i) => {
          const theme = mode === "light" ? base.light : base.theme;
          const Icon = base.icon;
          const live = meta?.[base.id];
          const tables = live?.tables ?? base.tables;
          const rows = live?.rows ?? base.rows;
          return (
            <motion.button
              key={base.id}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.12 * i, ease: [0.22, 1, 0.36, 1] }}
              whileHover={{ y: -8 }}
              onClick={() => onPick(base.id)}
              className="group relative overflow-hidden rounded-3xl border p-6 text-left backdrop-blur-xl"
              style={{
                borderColor: theme.border,
                background: theme.bg,
                boxShadow: `0 30px 70px -40px ${theme.glow}`,
              }}
            >
              <span
                className="pointer-events-none absolute inset-0 opacity-70 transition-opacity duration-500 group-hover:opacity-100"
                style={{ background: theme.texture }}
              />
              <span className="relative block">
                <span
                  className="grid size-12 place-items-center rounded-2xl"
                  style={{ background: theme.primary, color: theme.primaryFg }}
                >
                  <Icon className="size-6" />
                </span>
                <span
                  className="mt-5 block text-2xl font-bold"
                  style={{ color: theme.text, fontFamily: theme.display }}
                >
                  {base.label}
                </span>
                <span className="mt-1.5 block text-sm" style={{ color: theme.muted }}>
                  {base.tagline}
                </span>
                <span className="mt-6 flex items-center gap-2">
                  {[theme.primary, theme.accent, theme.text].map((c) => (
                    <span
                      key={c}
                      className="size-4 rounded-full ring-1 ring-black/10"
                      style={{ background: c }}
                    />
                  ))}
                  <span
                    className="ml-auto flex items-center gap-1.5 text-xs font-semibold transition-transform group-hover:translate-x-1"
                    style={{ color: theme.accent }}
                  >
                    {base.themeName} theme <ArrowRight className="size-3.5" />
                  </span>
                </span>
                <span
                  className="mt-4 flex gap-4 border-t pt-4 text-[11px]"
                  style={{ borderColor: theme.border, color: theme.muted }}
                >
                  <span>{tables} tables</span>
                  <span>{rows} rows</span>
                  <span>{base.engine}</span>
                </span>
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

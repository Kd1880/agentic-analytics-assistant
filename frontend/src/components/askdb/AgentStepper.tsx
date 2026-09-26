import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";

/**
 * The agent's pipeline, shown as it runs. Mirrors the real backend stages:
 * introspect -> retrieve examples -> generate -> guardrails -> execute ->
 * (self-correct) -> done.
 */

export const STEP_READ = "Reading schema";
export const STEP_RETRIEVE = "Retrieving examples";
export const STEP_WRITE = "Writing SQL";
export const STEP_SAFETY = "Safety check (SELECT-only)";
export const STEP_RUN = "Running query";
export const STEP_DONE = "Done";

export function buildSteps(opts: { memory: boolean; attempts: number }): string[] {
  return [
    STEP_READ,
    ...(opts.memory ? [STEP_RETRIEVE] : []),
    STEP_WRITE,
    STEP_SAFETY,
    STEP_RUN,
    ...(opts.attempts > 1 ? [`Self-correcting (attempt ${opts.attempts})`] : []),
    STEP_DONE,
  ];
}

export function AgentStepper({ labels, current }: { labels: string[]; current: number }) {
  return (
    <div className="flex flex-wrap gap-2">
      {labels.map((label, i) => {
        const done = i < current;
        const active = i === current;
        const isFix = label.startsWith("Self-correcting");
        return (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: done || active ? 1 : 0.4, y: 0, scale: active ? 1.02 : 1 }}
            transition={{ duration: 0.3, delay: i * 0.03 }}
            className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium"
            style={{
              borderColor: active || (isFix && done) ? "var(--primary)" : "var(--line)",
              background: active ? "var(--surface-strong)" : "var(--surface)",
              color: done || active ? "var(--text)" : "var(--muted)",
              boxShadow: active ? "0 0 24px -6px var(--glow)" : undefined,
            }}
          >
            {done ? (
              <Check className="size-3.5" style={{ color: "var(--primary)" }} />
            ) : active ? (
              <Loader2 className="size-3.5 animate-spin" style={{ color: "var(--primary)" }} />
            ) : (
              <span className="size-1.5 rounded-full" style={{ background: "var(--muted)" }} />
            )}
            {label}
          </motion.div>
        );
      })}
    </div>
  );
}

/** The SQL being "typed" while the agent works. */
export function TypedSql({ sql }: { sql: string }) {
  if (!sql) return null;
  return (
    <pre
      className="max-h-40 overflow-hidden rounded-2xl border p-3 font-mono text-[11px] leading-5"
      style={{
        borderColor: "var(--line)",
        background: "var(--surface-strong)",
        color: "var(--muted)",
      }}
    >
      {sql}
      <motion.span
        animate={{ opacity: [1, 0, 1] }}
        transition={{ duration: 0.9, repeat: Infinity }}
        className="inline-block w-1.5"
        style={{ background: "var(--primary)" }}
      >
        &nbsp;
      </motion.span>
    </pre>
  );
}

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeftRight, ArrowUp, Clock, Database, Table2, TriangleAlert } from "lucide-react";
import { ask, USE_MOCK, type AskResponse } from "@/lib/api";
import type { DatabaseConfig } from "@/lib/databases";
import { AgentStepper, TypedSql, buildSteps } from "./AgentStepper";
import { ResultPanel } from "./ResultPanel";
import { EmptyState } from "./EmptyState";

type HistoryItem = { id: number; question: string; result: AskResponse };

export function Workspace({
  db,
  onSwitch,
  toggle,
}: {
  db: DatabaseConfig;
  onSwitch: () => void;
  toggle?: React.ReactNode;
}) {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<string[]>([]);
  const [step, setStep] = useState(0);
  const [pending, setPending] = useState("");
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    setHistory([]);
    setActiveId(null);
    setInput("");
    setError(null);
  }, [db.id]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const active = history.find((h) => h.id === activeId) ?? null;

  /** Reveal the returned SQL character by character while we finish the stepper. */
  function typeOut(sql: string) {
    const clipped = sql.slice(0, 260);
    let i = 0;
    const tick = () => {
      i += Math.max(2, Math.round(clipped.length / 40));
      setTyped(clipped.slice(0, i));
      if (i < clipped.length) timers.current.push(setTimeout(tick, 22));
    };
    tick();
  }

  async function submit(question: string) {
    const q = question.trim();
    if (!q || running) return;
    setInput("");
    setPending(q);
    setRunning(true);
    setActiveId(null);
    setError(null);
    setTyped("");

    const promise = ask(db.id, q);

    // Optimistic stepper: advance through the stages we know happen up front.
    const preview = buildSteps({ memory: true, attempts: 1 });
    setSteps(preview);
    setStep(0);
    timers.current.forEach(clearTimeout);
    timers.current = [0, 1, 2].map((i) => setTimeout(() => setStep(i + 1), 300 * (i + 1)));

    try {
      const result = await promise;
      const full = buildSteps({ memory: true, attempts: result.attempts });
      setSteps(full);
      // park on "Running query" (or the self-correct step) while the SQL types out
      setStep(full.length - (result.attempts > 1 ? 2 : 1));
      typeOut(result.sql);
      await new Promise((r) => setTimeout(r, result.attempts > 1 ? 900 : 500));
      setStep(full.length);

      const item: HistoryItem = { id: Date.now(), question: q, result };
      setHistory((h) => [item, ...h]);
      setActiveId(item.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      timers.current.forEach(clearTimeout);
      setRunning(false);
      setPending("");
      setTyped("");
    }
  }

  const Icon = db.icon;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 pb-20 sm:px-6">
      <header
        className="sticky top-3 z-20 mt-3 flex flex-wrap items-center gap-3 rounded-2xl border px-4 py-3 backdrop-blur-xl sm:gap-4"
        style={{
          borderColor: "var(--line)",
          background: "var(--surface-strong)",
          boxShadow: "0 24px 60px -40px var(--glow)",
        }}
      >
        <span
          className="grid size-10 shrink-0 place-items-center rounded-xl"
          style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
        >
          <Icon className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p
            className="truncate text-base leading-tight font-semibold"
            style={{ color: "var(--text)", fontFamily: "var(--display)" }}
          >
            {db.label}
          </p>
          <p className="truncate text-xs" style={{ color: "var(--muted)" }}>
            {db.themeName} theme · {db.tagline}
          </p>
        </div>
        <div
          className="hidden items-center gap-4 text-xs sm:flex"
          style={{ color: "var(--muted)" }}
        >
          <span className="flex items-center gap-1.5">
            <Table2 className="size-3.5" /> {db.tables} tables
          </span>
          <span className="flex items-center gap-1.5">
            <Database className="size-3.5" /> {db.rows} rows
          </span>
          {USE_MOCK ? (
            <span
              className="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
              style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
            >
              MOCK
            </span>
          ) : null}
        </div>
        {toggle}
        <button
          onClick={onSwitch}
          className="flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-transform hover:scale-[1.03]"
          style={{
            borderColor: "var(--line)",
            color: "var(--text)",
            background: "var(--surface)",
          }}
        >
          <ArrowLeftRight className="size-3.5" />
          Switch database
        </button>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_260px]">
        <div className="min-w-0 space-y-5">
          <div
            className="rounded-3xl border p-2 backdrop-blur-xl"
            style={{
              borderColor: "var(--line)",
              background: "var(--surface)",
              boxShadow: "0 30px 80px -50px var(--glow)",
            }}
          >
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void submit(input);
              }}
              className="flex items-center gap-2"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={db.placeholder}
                className="min-w-0 flex-1 bg-transparent px-4 py-3 text-sm outline-none placeholder:opacity-60"
                style={{ color: "var(--text)" }}
              />
              <button
                type="submit"
                disabled={running || !input.trim()}
                className="grid size-10 shrink-0 place-items-center rounded-2xl transition-transform hover:scale-105 disabled:opacity-40"
                style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
                aria-label="Send question"
              >
                <ArrowUp className="size-4" />
              </button>
            </form>
          </div>

          <div className="flex flex-wrap gap-2">
            {db.chips.map((chip) => (
              <button
                key={chip}
                onClick={() => setInput(chip)}
                className="max-w-full truncate rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all hover:scale-[1.04]"
                style={{
                  borderColor: "var(--line)",
                  background: "var(--surface)",
                  color: "var(--muted)",
                }}
              >
                {chip}
              </button>
            ))}
          </div>

          {error ? (
            <div
              className="flex gap-3 rounded-2xl border p-4 text-sm"
              style={{ borderColor: "var(--accent)", background: "var(--surface-strong)" }}
            >
              <TriangleAlert className="mt-0.5 size-4 shrink-0" style={{ color: "var(--accent)" }} />
              <span style={{ color: "var(--text)" }}>{error}</span>
            </div>
          ) : null}

          <AnimatePresence mode="wait">
            {running ? (
              <motion.div
                key="running"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-4 rounded-3xl border p-5 backdrop-blur-xl"
                style={{ borderColor: "var(--line)", background: "var(--surface)" }}
              >
                <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
                  {pending}
                </p>
                <AgentStepper labels={steps} current={step} />
                <TypedSql sql={typed} />
              </motion.div>
            ) : active ? (
              <ResultPanel
                key={active.id}
                result={active.result}
                db={db}
                question={active.question}
              />
            ) : (
              <EmptyState key={`empty-${db.id}`} db={db.id} />
            )}
          </AnimatePresence>
        </div>

        <aside className="space-y-2">
          <p
            className="flex items-center gap-2 px-1 text-[11px] font-semibold tracking-wider uppercase"
            style={{ color: "var(--muted)" }}
          >
            <Clock className="size-3.5" /> Session history
          </p>
          {history.length === 0 ? (
            <p
              className="rounded-2xl border px-3 py-4 text-xs"
              style={{
                borderColor: "var(--line)",
                background: "var(--surface)",
                color: "var(--muted)",
              }}
            >
              Your past questions will appear here.
            </p>
          ) : (
            history.map((h) => (
              <button
                key={h.id}
                onClick={() => setActiveId(h.id)}
                className="w-full rounded-2xl border px-3 py-3 text-left text-xs transition-colors"
                style={{
                  borderColor: h.id === activeId ? "var(--primary)" : "var(--line)",
                  background: h.id === activeId ? "var(--surface-strong)" : "var(--surface)",
                  color: "var(--text)",
                }}
              >
                <span className="line-clamp-2">{h.question}</span>
                <span className="mt-1 block" style={{ color: "var(--muted)" }}>
                  {h.result.rows.length} rows · attempt {h.result.attempts}
                </span>
              </button>
            ))
          )}
        </aside>
      </div>
    </div>
  );
}

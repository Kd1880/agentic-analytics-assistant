import { useState } from "react";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, Check, Copy, Server, Sparkles } from "lucide-react";
import type { AskResponse } from "@/lib/api";
import type { DatabaseConfig } from "@/lib/databases";

const TABS = ["Answer", "Chart", "SQL"] as const;
type Tab = (typeof TABS)[number];

function Chip({ children, tone }: { children: React.ReactNode; tone?: "primary" | "warn" }) {
  if (tone === "primary") {
    return (
      <span
        className="rounded-full px-2.5 py-1 text-[11px] font-semibold"
        style={{ background: "var(--primary)", color: "var(--primary-fg)" }}
      >
        {children}
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium"
      style={{
        borderColor: tone === "warn" ? "var(--accent)" : "var(--line)",
        background: "var(--surface)",
        color: "var(--text)",
      }}
    >
      {children}
    </span>
  );
}

const KEYWORD_LIST =
  "SELECT|FROM|WHERE|GROUP BY|ORDER BY|LIMIT|JOIN|LEFT JOIN|CROSS JOIN|INNER JOIN|ON|HAVING|AS|AND|OR|NOT|EXISTS|CASE|WHEN|THEN|ELSE|END|COUNT|AVG|SUM|MAX|MIN|ROUND|DESC|ASC|DISTINCT|OVER|PARTITION BY|EXTRACT|EPOCH|date_trunc|unnest|string_to_array|substring|WITH|UNION ALL|IS|NULL";
const SPLIT_RE = new RegExp(`\\b(${KEYWORD_LIST})\\b`, "g");
const IS_KEYWORD = new RegExp(`^(${KEYWORD_LIST})$`);

function highlight(sql: string) {
  return sql.split("\n").map((line, i) => {
    const parts = line.split(SPLIT_RE);
    return (
      <div key={i} className="whitespace-pre">
        {parts.map((p, j) =>
          IS_KEYWORD.test(p) ? (
            <span key={j} style={{ color: "var(--primary)", fontWeight: 600 }}>
              {p}
            </span>
          ) : (
            <span key={j} style={{ color: "var(--text)" }}>
              {p}
            </span>
          ),
        )}
      </div>
    );
  });
}

export function ResultPanel({
  result,
  db,
  question,
}: {
  result: AskResponse;
  db: DatabaseConfig;
  question: string;
}) {
  const [tab, setTab] = useState<Tab>("Answer");
  const [copied, setCopied] = useState(false);

  const hint = result.chartHint;
  const chartable = hint.type === "bar" || hint.type === "line";

  const chartData = result.rows.map((r) => {
    const o: Record<string, string | number> = {};
    result.columns.forEach((c, i) => {
      const v = r[i];
      o[c] = v === null ? "" : v;
    });
    return o;
  });

  // Prefer the backend's hint; fall back to "first column vs first numeric column".
  const xKey = chartable && "x" in hint ? hint.x : (result.columns[0] ?? "");
  const yKey =
    chartable && "y" in hint && result.columns.includes(hint.y)
      ? hint.y
      : (result.columns.find((_c, i) => i > 0 && typeof result.rows[0]?.[i] === "number") ??
        result.columns[1] ??
        "");

  const copy = () => {
    void navigator.clipboard.writeText(result.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="overflow-hidden rounded-3xl border backdrop-blur-xl"
      style={{
        borderColor: "var(--line)",
        background: "var(--surface)",
        boxShadow: "0 30px 80px -40px var(--glow)",
      }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4"
        style={{ borderColor: "var(--line)" }}
      >
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold" style={{ color: "var(--text)" }}>
            {question}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Chip>{result.succeeded ? "Executed ✓" : "Failed"}</Chip>
            <Chip>{result.rows.length} rows</Chip>
            {result.attempts > 1 ? (
              <Chip tone="primary">Fixed on attempt {result.attempts}</Chip>
            ) : (
              <Chip>Attempt 1</Chip>
            )}
            <Chip>
              <Server className="size-3" /> {result.provider}
            </Chip>
            {result.elapsedMs ? <Chip>{(result.elapsedMs / 1000).toFixed(1)}s</Chip> : null}
            {result.truncated ? <Chip tone="warn">display capped</Chip> : null}
          </div>
          {result.providerFallback ? (
            <p
              className="mt-2 flex items-start gap-1.5 text-[11px]"
              style={{ color: "var(--accent)" }}
            >
              <AlertTriangle className="mt-px size-3 shrink-0" />
              {result.providerFallback}
            </p>
          ) : null}
        </div>
        <div
          className="flex rounded-full border p-1"
          style={{ borderColor: "var(--line)", background: "var(--surface)" }}
        >
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="relative rounded-full px-4 py-1.5 text-xs font-semibold transition-colors"
              style={{ color: tab === t ? "var(--primary-fg)" : "var(--muted)" }}
            >
              {tab === t && (
                <motion.span
                  layoutId="result-tab"
                  className="absolute inset-0 rounded-full"
                  style={{ background: "var(--primary)" }}
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                />
              )}
              <span className="relative">{t}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="p-5">
        {tab === "Answer" && (
          <div className="space-y-4">
            <div
              className="flex gap-3 rounded-2xl border p-4"
              style={{ borderColor: "var(--line)", background: "var(--surface-strong)" }}
            >
              <Sparkles className="mt-0.5 size-4 shrink-0" style={{ color: "var(--accent)" }} />
              <p className="text-sm leading-relaxed" style={{ color: "var(--text)" }}>
                {result.insight}
              </p>
            </div>
            {result.rows.length === 0 ? (
              <p className="py-6 text-center text-sm" style={{ color: "var(--muted)" }}>
                No rows returned.
              </p>
            ) : (
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full min-w-[420px] border-collapse text-sm">
                  <thead>
                    <tr>
                      {result.columns.map((c) => (
                        <th
                          key={c}
                          className="sticky top-0 border-b px-3 py-2 text-left text-[11px] font-semibold tracking-wider uppercase backdrop-blur"
                          style={{
                            borderColor: "var(--line)",
                            color: "var(--muted)",
                            background: "var(--surface-strong)",
                          }}
                        >
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i} className="transition-colors hover:bg-[var(--surface)]">
                        {row.map((cell, j) => (
                          <td
                            key={j}
                            className="border-b px-3 py-2 tabular-nums"
                            style={{
                              borderColor: "var(--line)",
                              color: j === 0 ? "var(--text)" : "var(--muted)",
                              fontWeight: j === 0 ? 500 : 400,
                            }}
                          >
                            {cell === null
                              ? "NULL"
                              : typeof cell === "number"
                                ? cell.toLocaleString("en-US", { maximumFractionDigits: 4 })
                                : cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {tab === "Chart" &&
          (!chartable ? (
            <p className="py-10 text-center text-sm" style={{ color: "var(--muted)" }}>
              {hint.type === "scalar"
                ? "A single value — nothing to plot."
                : "This result isn't suited to a chart."}
            </p>
          ) : (
            <div className="h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                {hint.type === "line" ? (
                  <LineChart data={chartData} margin={{ left: -12, right: 12, top: 10 }}>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis
                      dataKey={xKey}
                      tick={{ fill: "var(--muted)", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{ fill: "var(--muted)", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: db.theme.bg,
                        border: `1px solid ${db.theme.border}`,
                        borderRadius: 12,
                        color: db.theme.text,
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey={yKey}
                      stroke={db.theme.primary}
                      strokeWidth={2.5}
                      dot={{ fill: db.theme.accent, r: 3 }}
                    />
                  </LineChart>
                ) : (
                  <BarChart data={chartData} margin={{ left: -12, right: 12, top: 10 }}>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis
                      dataKey={xKey}
                      tick={{ fill: "var(--muted)", fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      interval={0}
                      height={70}
                      angle={-25}
                      textAnchor="end"
                    />
                    <YAxis
                      tick={{ fill: "var(--muted)", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: db.theme.surface }}
                      contentStyle={{
                        background: db.theme.bg,
                        border: `1px solid ${db.theme.border}`,
                        borderRadius: 12,
                        color: db.theme.text,
                      }}
                    />
                    <Bar dataKey={yKey} fill={db.theme.primary} radius={[6, 6, 0, 0]} />
                  </BarChart>
                )}
              </ResponsiveContainer>
            </div>
          ))}

        {tab === "SQL" && (
          <div
            className="relative rounded-2xl border p-4"
            style={{ borderColor: "var(--line)", background: "var(--surface-strong)" }}
          >
            <button
              onClick={copy}
              className="absolute top-3 right-3 flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-opacity hover:opacity-80"
              style={{
                borderColor: "var(--line)",
                color: "var(--text)",
                background: "var(--surface-strong)",
              }}
            >
              {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <pre className="overflow-x-auto font-mono text-xs leading-6">
              {highlight(result.sql || "-- no SQL was produced")}
            </pre>
          </div>
        )}
      </div>
    </motion.div>
  );
}

import type { DbId } from "./databases";
import { mockAnswer } from "./mockData";

/**
 * The ONLY integration point with the backend.
 *
 * The browser never talks to an LLM provider directly and never holds an API
 * key — it only calls this project's own FastAPI backend, whose URL comes from
 * VITE_API_URL. Set VITE_USE_MOCK=false to use the real backend.
 */

export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000";

export const USE_MOCK: boolean =
  (import.meta.env.VITE_USE_MOCK as string | undefined) !== "false";

export type ChartHint =
  | { type: "bar" | "line"; x: string; y: string }
  | { type: "scalar"; label: string }
  | { type: "table" }
  | { type: "none" };

export type AskResponse = {
  sql: string;
  columns: string[];
  rows: (string | number | null)[][];
  attempts: number;
  succeeded: boolean;
  insight: string;
  chartHint: ChartHint;
  provider: string;
  providerFallback?: string | null;
  truncated?: boolean;
  elapsedMs?: number;
};

export type DatabaseMeta = {
  /** GET /databases returns the key as `name`; `id` is accepted too. */
  id?: DbId;
  name?: string;
  label?: string;
  tagline?: string;
  tables?: number;
  rows?: number | string;
  dialect?: string;
  status?: string;
};

/** The backend may send chartHint as an object (current) or a bare string (older). */
function normaliseHint(hint: unknown, columns: string[]): ChartHint {
  if (typeof hint === "string") {
    if (hint === "bar" || hint === "line") {
      return { type: hint, x: columns[0] ?? "", y: columns[1] ?? "" };
    }
    return { type: "none" };
  }
  if (hint && typeof hint === "object" && "type" in hint) return hint as ChartHint;
  return { type: "none" };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (err) {
    // A failed fetch with no status is nearly always CORS or a backend that is down.
    throw new Error(
      `Could not reach the backend at ${API_URL}. Is it running ` +
        `(uvicorn backend.app:app --port 8000)? If it is, this origin may need to be ` +
        `added to the backend's ALLOWED_ORIGINS. (${(err as Error).message})`,
    );
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export async function getDatabases(): Promise<DatabaseMeta[]> {
  if (USE_MOCK) return [];
  const data = await request<{ databases: DatabaseMeta[] }>("/databases");
  return (data.databases ?? []).filter((d) => d.status !== "error");
}

export async function ask(db: DbId, question: string): Promise<AskResponse> {
  if (USE_MOCK) return mockAnswer(db, question);

  const raw = await request<Record<string, unknown>>("/ask", {
    method: "POST",
    body: JSON.stringify({ db, question }),
  });

  const columns = (raw.columns as string[]) ?? [];
  return {
    sql: (raw.sql as string) ?? "",
    columns,
    rows: (raw.rows as (string | number | null)[][]) ?? [],
    attempts: (raw.attempts as number) ?? 1,
    succeeded: Boolean(raw.succeeded),
    insight: (raw.insight as string) ?? "",
    chartHint: normaliseHint(raw.chartHint, columns),
    provider: (raw.provider as string) ?? "unknown",
    providerFallback: (raw.providerFallback as string | null) ?? null,
    truncated: Boolean(raw.truncated),
    elapsedMs: raw.elapsedMs as number | undefined,
  };
}

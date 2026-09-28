import type { SourceKey } from "@/lib/sources";

export interface ProjectUsage {
  total_tokens: number;
  cost: number;
  messages: number;
  session_count: number;
  by_source: string[];
}

export interface SessionDetailEntry {
  session_id: string;
  tokens: number;
  cost: number;
  title: string | null;
  first_ts: string | number | null;
  last_ts: string | number | null;
  cwd: string | null;
  date: string | null;
}

export interface SourceProjectUsage {
  input: number;
  output: number;
  cache_read: number;
  cache_write: number;
  total_tokens: number;
  cost: number;
  cost_incomplete?: boolean;
  messages: number;
  session_count: number;
  by_day: Record<string, { tokens: number; cost: number }>;
  sessions_detail: SessionDetailEntry[];
}

export interface OpenRouterUsage {
  unavailable: boolean;
  reason?: string;
  models?: Record<string, { tokens: number; cost: number; requests: number }>;
  by_day?: Record<string, { tokens: number; cost: number }>;
}

export interface UsageSnapshot {
  sources: {
    claude_code: Record<string, SourceProjectUsage>;
    codex: Record<string, SourceProjectUsage>;
    opencode: Record<string, SourceProjectUsage>;
    hermes: Record<string, SourceProjectUsage>;
    openrouter: OpenRouterUsage;
  };
  combined: Record<string, ProjectUsage>;
}

export interface RoiSettings {
  subscription_cost_claude: number | null;
  subscription_cost_codex: number | null;
  hourly_rate: number | null;
  subscription_start_claude: string | null;
  subscription_start_codex: string | null;
}

export interface DailyProjectRow {
  date: string;
  source: string;
  project: string;
  tokens: number;
  cost: number | null;
}

export interface DailyModelRow {
  date: string;
  model: string;
  tokens: number;
  cost: number;
}

export interface HistoryResponse {
  daily_project: DailyProjectRow[];
  daily_model: DailyModelRow[];
}

/** Error HTTP con el status, para que la UI distinga un 400 (parámetro inválido) de una caída. */
export class HttpError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "HttpError";
    this.status = status;
  }
}

/** fetch + JSON que falla con un Error legible si el servidor responde != 2xx
 * (sin esto un 500 llega como JSON de error y se trata como datos válidos). */
async function getJson<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init);
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) detail = `: ${body.error}`;
    } catch {
      // cuerpo no JSON: basta con el status
    }
    throw new HttpError(`${init?.method ?? "GET"} ${input} → HTTP ${res.status}${detail}`, res.status);
  }
  return res.json() as Promise<T>;
}

/** Qué opción sale más barata para el mismo consumo (usado por roi.ts y el briefing). */
export type CostWinner = "subscription" | "api" | "tie";

export type Coverage = "full" | "partial" | "none";

export interface MonthCoverage {
  month: string;
  coverage: Exclude<Coverage, "none">;
  since: string | null;
}

export interface BriefingKpi {
  current: number;
  previous: number | null;
  delta_pct: number | null;
}

export interface BriefingSignal {
  id: string;
  severity: "warning" | "info";
  title: string;
  evidence: string[];
  link: string;
}

export interface BriefingSubscription {
  configured: boolean;
  paid: number | null;
  api_equivalent: number | null;
  winner: CostWinner | null;
  savings: number | null;
}

export interface BriefingProject {
  project: string;
  client: string;
  cost: number;
  share: number;
}

export interface BriefingResponse {
  source: SourceKey;
  window: { month: string; from: string; to: string };
  compare: { month: string; from: string; to: string; coverage: Coverage; since: string | null };
  eligible_months: MonthCoverage[];
  kpis: {
    cost: BriefingKpi;
    tokens: BriefingKpi;
    active_days: { current: number; previous: number | null };
    cost_incomplete: boolean;
  };
  subscription: BriefingSubscription;
  top_projects: BriefingProject[];
  attention: BriefingSignal[];
  degraded: boolean;
}

export function fetchBriefing(source: SourceKey, compare: string | null): Promise<BriefingResponse> {
  const params = new URLSearchParams({ source });
  if (compare) params.set("compare", compare);
  return getJson(`/api/briefing?${params}`);
}

export function fetchHistory(days: number): Promise<HistoryResponse> {
  return getJson(`/api/history?days=${days}`);
}

export function fetchRoiSettings(): Promise<RoiSettings> {
  return getJson("/api/roi-settings");
}

export function saveRoiSettings(settings: Partial<RoiSettings>): Promise<RoiSettings> {
  return getJson("/api/roi-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

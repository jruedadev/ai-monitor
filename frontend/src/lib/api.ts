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
}

export async function fetchRoiSettings(): Promise<RoiSettings> {
  const res = await fetch("/api/roi-settings");
  return res.json();
}

export async function saveRoiSettings(settings: Partial<RoiSettings>): Promise<RoiSettings> {
  const res = await fetch("/api/roi-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  return res.json();
}

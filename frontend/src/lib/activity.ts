import type { UsageSnapshot } from "@/lib/api";
import { OFFICE_MAX_AGENTS, basename, deriveOfficeAgents, type OfficeAgent } from "@/lib/office";

export type ActivityState = "tool" | "waiting" | "thinking" | "idle";
export type ToolKind = "edit" | "read" | "run" | "other";

export interface ActivityAgent {
  key: string;
  source: string;
  project: string;
  state: ActivityState;
  tool: string | null;
  tool_kind: ToolKind | null;
  since: string;
}

export interface ActivitySnapshot {
  generated_at: string | null;
  agents: ActivityAgent[];
  sources: Record<string, "ok" | "unavailable">;
}

/** Fuentes con detección en vivo; Codex solo tiene el estado básico de /api/usage. */
export const LIVE_SOURCES = ["claude_code", "opencode", "hermes"] as const;
const isLiveSource = (s: string): s is (typeof LIVE_SOURCES)[number] => (LIVE_SOURCES as readonly string[]).includes(s);

export function mergeOfficeAgents(
  activity: ActivitySnapshot | null,
  sources: UsageSnapshot["sources"] | null | undefined,
  nowMs: number,
  limit: number = OFFICE_MAX_AGENTS,
): OfficeAgent[] {
  const byKey = new Map<string, OfficeAgent>();
  for (const a of deriveOfficeAgents(sources, nowMs, Infinity)) {
    const liveOk = isLiveSource(a.source) && activity?.sources[a.source] === "ok";
    if (!liveOk) byKey.set(a.key, a);
  }
  for (const a of activity?.agents ?? []) {
    const sinceMs = Date.parse(a.since);
    if (!isLiveSource(a.source) || activity?.sources[a.source] !== "ok" || Number.isNaN(sinceMs)) continue;
    byKey.set(a.key, {
      key: a.key,
      source: a.source,
      project: a.project,
      label: basename(a.project),
      state: a.state,
      tool: a.tool,
      toolKind: a.tool_kind,
      sinceMs,
      live: true,
    });
  }
  return [...byKey.values()].sort((a, b) => b.sinceMs - a.sinceMs).slice(0, limit);
}

const isSnapshot = (v: unknown): v is ActivitySnapshot =>
  typeof v === "object" && v !== null && Array.isArray((v as ActivitySnapshot).agents) &&
  typeof (v as ActivitySnapshot).sources === "object";

/** Snapshot inicial; null si falla (la vista sigue con el estado básico hasta el primer evento SSE). */
export async function fetchActivity(fetchImpl: typeof fetch = fetch, timeoutMs = 5_000): Promise<ActivitySnapshot | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl("/api/activity", { signal: controller.signal });
    if (!res.ok) return null;
    const body: unknown = await res.json();
    return isSnapshot(body) ? body : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

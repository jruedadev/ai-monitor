import type { SourceKey } from "@/lib/sources";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";

export interface FlatSession extends SessionDetailEntry {
  source: string;
  project: string;
}

/** Fuentes con sessions_detail comparable — OpenRouter queda fuera (agrega por modelo, no por sesión). */
export const SESSION_SOURCES = ["claude_code", "codex", "opencode", "hermes"] as const;

export function collectSessions(
  sources: UsageSnapshot["sources"] | null | undefined,
  section: SourceKey,
  project?: string,
): FlatSession[] {
  if (!sources) return [];
  const sourceKeys = section === "all" ? SESSION_SOURCES : section === "openrouter" ? [] : ([section] as const);

  const rows: FlatSession[] = [];
  for (const key of sourceKeys) {
    for (const [name, usage] of Object.entries(sources[key] ?? {})) {
      if (project && name !== project) continue;
      for (const session of usage.sessions_detail) {
        rows.push({ ...session, source: key, project: name });
      }
    }
  }
  return rows;
}

/**
 * claude_code usa ISO (string), codex y hermes epoch en segundos y opencode epoch en ms.
 * Un número > 1e12 ya está en ms (1e12 s sería el año 33658).
 */
export function toEpochMs(ts: string | number | null): number | null {
  if (ts === null) return null;
  const ms = typeof ts === "number" ? (ts > 1e12 ? ts : ts * 1000) : Date.parse(ts);
  return Number.isNaN(ms) ? null : ms;
}

export function sessionDurationSeconds(session: Pick<SessionDetailEntry, "first_ts" | "last_ts">): number {
  const start = toEpochMs(session.first_ts);
  const end = toEpochMs(session.last_ts);
  if (start === null || end === null || end < start) return 0;
  return (end - start) / 1000;
}

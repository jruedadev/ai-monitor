import type { SectionKey } from "@/components/Sidebar";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";

export interface FlatSession extends SessionDetailEntry {
  source: string;
  project: string;
}

/** Fuentes con sessions_detail comparable — OpenRouter queda fuera (agrega por modelo, no por sesión). */
export const SESSION_SOURCES = ["claude_code", "codex", "opencode"] as const;

export function collectSessions(
  sources: UsageSnapshot["sources"] | null | undefined,
  section: SectionKey,
  project?: string,
): FlatSession[] {
  if (!sources) return [];
  const sourceKeys = section === "all"
    ? SESSION_SOURCES
    : section === "openrouter" ? [] : ([section] as const);

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

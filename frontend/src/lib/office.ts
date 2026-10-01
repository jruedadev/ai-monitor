/**
 * Oficina pixel-art: estado básico de las sesiones a partir de /api/usage (granularidad del
 * colector, ~60 s). La actividad en vivo (herramienta en curso) llega por /api/activity y se
 * fusiona en lib/activity.ts.
 */
import { SESSION_SOURCES, collectSessions, toEpochMs } from "@/lib/sessions";
import type { UsageSnapshot } from "@/lib/api";
import type { ActivityState, ToolKind } from "@/lib/activity";

/** Una sesión con actividad en esta ventana tiene personaje en la oficina. */
export const OFFICE_WINDOW_MS = 30 * 60_000;
/** Estado básico: activa hace menos de esto → "thinking"; después → "idle". */
export const BASIC_THINKING_MS = 3 * 60_000;
export const OFFICE_MAX_AGENTS = 12;
/** Tolerancia de reloj: una marca algo adelantada sigue contando como "ahora". */
const CLOCK_SKEW_MS = 60_000;

export interface OfficeAgent {
  key: string;
  source: (typeof SESSION_SOURCES)[number];
  project: string;
  label: string;
  state: ActivityState;
  tool: string | null;
  toolKind: ToolKind | null;
  sinceMs: number;
  /** true si vino de /api/activity; false si es el estado básico de /api/usage. */
  live: boolean;
}

export function basename(path: string): string {
  return path.split("/").filter(Boolean).pop() ?? path;
}

export function deriveOfficeAgents(
  sources: UsageSnapshot["sources"] | null | undefined,
  nowMs: number,
  limit: number = OFFICE_MAX_AGENTS,
): OfficeAgent[] {
  const agents: OfficeAgent[] = [];
  for (const s of collectSessions(sources, "all")) {
    const lastMs = toEpochMs(s.last_ts);
    if (lastMs === null || lastMs > nowMs + CLOCK_SKEW_MS || nowMs - lastMs > OFFICE_WINDOW_MS) continue;
    agents.push({
      key: `${s.source}:${s.session_id}`,
      source: s.source as OfficeAgent["source"],
      project: s.project,
      label: basename(s.project),
      state: nowMs - lastMs < BASIC_THINKING_MS ? "thinking" : "idle",
      tool: null,
      toolKind: null,
      sinceMs: lastMs,
      live: false,
    });
  }
  return agents.sort((a, b) => b.sinceMs - a.sinceMs).slice(0, limit);
}

/** Lógica pura de la vista Recomendaciones (testeable sin DOM). */
import {
  HttpError, type CostEvidence, type EngineBackend, type Recommendation, type RecommendationImpact,
  type RecommendationKind, type RecommendationRun, type RecommendationStatus, type RecommendationsResponse,
} from "@/lib/api";
import { formatCompact } from "@/lib/format";
import type { SourceKey } from "@/lib/sources";
import { basename } from "@/lib/tree";

export const REC_TABS: { status: RecommendationStatus; label: string }[] = [
  { status: "nueva", label: "Nuevas" },
  { status: "aplicada", label: "Aplicadas" },
  { status: "saltada", label: "Saltadas" },
  { status: "resuelta", label: "Resueltas" },
];

export function parseRecTab(value: string | null): RecommendationStatus {
  return REC_TABS.find((t) => t.status === value)?.status ?? "nueva";
}

export const KIND_LABEL: Record<RecommendationKind, string> = {
  skill: "Skill", plugin: "Plugin", prompt: "Prompt", costo: "Costo",
};

export const IMPACT_LABEL: Record<RecommendationImpact, string> = {
  alto: "Impacto alto", medio: "Impacto medio", bajo: "Impacto bajo",
};

export const BACKEND_OPTIONS: { value: EngineBackend; label: string; hint: string }[] = [
  { value: "hermes", label: "Hermes", hint: "Modelos free en cadena; no consume tu suscripción." },
  { value: "claude", label: "claude -p", hint: "Usa tu suscripción de Claude; aparece como proyecto motor-recomendaciones." },
  { value: "none", label: "Ninguno", hint: "Solo reglas locales: agrupación léxica y textos por plantilla." },
];

export function isCostEvidence(evidence: Recommendation["evidence"]): evidence is CostEvidence {
  return "rule" in evidence;
}

/** ?fuente=: la fuente única de la recomendación o cualquiera de las de un patrón compartido. */
export function filterBySource(recs: Recommendation[], source: SourceKey): Recommendation[] {
  if (source === "all") return recs;
  return recs.filter((r) => r.tool === source || r.evidence.sources.includes(source));
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function evidenceLines(rec: Recommendation): string[] {
  const ev = rec.evidence;
  if (isCostEvidence(ev)) return ev.items;
  const lines = [
    `${plural(ev.sessions, "sesión", "sesiones")} en ${plural(ev.days, "día", "días")}`,
    `${formatCompact(ev.tokens)} tokens`,
  ];
  if (ev.projects.length) lines.push(`Proyectos: ${ev.projects.map(basename).join(", ")}`);
  return lines;
}

export function runErrorMessage(err: unknown): string {
  if (err instanceof HttpError && err.status === 409) return "Ya hay una corrida en curso";
  return `No se pudo iniciar el análisis (${err instanceof Error ? err.message : String(err)})`;
}

export interface Removed {
  rec: Recommendation;
  index: number;
}

/** Acción optimista: la tarjeta sale de la pestaña actual antes de que responda el servidor. */
export function removeRecommendation(list: Recommendation[], id: string): { next: Recommendation[]; removed: Removed | null } {
  const index = list.findIndex((r) => r.id === id);
  if (index < 0) return { next: list, removed: null };
  return { next: [...list.slice(0, index), ...list.slice(index + 1)], removed: { rec: list[index], index } };
}

/** Reversión si el servidor rechaza el cambio. */
export function restoreRecommendation(list: Recommendation[], removed: Removed | null): Recommendation[] {
  if (!removed || list.some((r) => r.id === removed.rec.id)) return list;
  const index = Math.min(removed.index, list.length);
  return [...list.slice(0, index), removed.rec, ...list.slice(index)];
}

const EMPTY: Record<RecommendationStatus, string> = {
  nueva: "Sin patrones repetidos en los últimos 30 días",
  aplicada: "No has aplicado ninguna recomendación",
  saltada: "No has saltado ninguna recomendación",
  resuelta: "Ninguna recomendación se ha resuelto todavía",
};

export function emptyMessage(tab: RecommendationStatus, lastRun: RecommendationRun | null): string {
  return lastRun ? EMPTY[tab] : "Aún no hay corridas: pulsa Analizar ahora";
}

export function runModelLabel(run: RecommendationRun): string {
  if (!run.model) return "reglas locales";
  return run.backend === "claude" ? "claude -p" : run.model;
}

/** En curso si el servidor lo dice o si la corrida que pidió esta pestaña aún no aparece terminada. */
export function isRunInProgress(data: RecommendationsResponse | null, pendingRunId: number | null): boolean {
  if (data?.running) return true;
  if (pendingRunId === null) return false;
  const last = data?.last_run;
  return !last || last.id < pendingRunId || last.finished_at === null;
}

export function recommendationsLine(count: number): string {
  return count === 1 ? "1 recomendación nueva →" : `${count} recomendaciones nuevas →`;
}

export function parseChain(text: string): string[] {
  return text.split("\n").map((line) => line.trim()).filter(Boolean);
}
import type { UsageSnapshot } from "@/lib/api";
import { SOURCE_META, type SourceKey } from "@/lib/sources";

export interface SourceStatus {
  key: Exclude<SourceKey, "all">;
  label: string;
  state: "data" | "empty" | "unavailable";
  detail: string;
}

const PROJECT_SOURCES = ["claude_code", "codex", "opencode", "hermes"] as const;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Estado por fuente a partir del snapshot en memoria. No distingue "no instalado" de
 * "falla de lectura": los collectors aún no reportan su estado (fuera de alcance v1). */
export function sourceStatuses(sources: UsageSnapshot["sources"] | null): SourceStatus[] {
  if (!sources) return [];
  const rows: SourceStatus[] = PROJECT_SOURCES.map((key) => {
    const count = Object.keys(sources[key] ?? {}).length;
    return {
      key,
      label: SOURCE_META[key].label,
      state: count > 0 ? "data" : "empty",
      detail: count > 0 ? plural(count, "proyecto", "proyectos") : "Sin datos (no instalado o sin uso)",
    };
  });
  const or = sources.openrouter;
  rows.push(
    or?.unavailable
      ? { key: "openrouter", label: SOURCE_META.openrouter.label, state: "unavailable", detail: or.reason ?? "No disponible" }
      : {
          key: "openrouter",
          label: SOURCE_META.openrouter.label,
          state: "data",
          detail: plural(Object.keys(or?.models ?? {}).length, "modelo", "modelos"),
        },
  );
  return rows;
}

/** Rutas de proyecto de las fuentes por proyecto (sin OpenRouter), ordenadas y sin duplicar. */
export function projectPaths(sources: UsageSnapshot["sources"] | null): string[] {
  if (!sources) return [];
  return [...new Set(PROJECT_SOURCES.flatMap((key) => Object.keys(sources[key] ?? {})))].sort();
}

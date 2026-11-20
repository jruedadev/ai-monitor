import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { clientOf, type ClientRoot } from "@/lib/clients";
import { snapshotKeys, type SourceKey } from "@/lib/sources";

/** Proyectos (o modelos, en OpenRouter) para una fuente, opcionalmente acotados a un cliente. */
export function projectsFor(
  sources: UsageSnapshot["sources"] | null,
  combined: Record<string, ProjectUsage> | null,
  source: SourceKey,
  client: string | null,
  roots: ClientRoot[],
): Record<string, ProjectUsage> {
  if (!sources || !combined) return {};

  let result: Record<string, ProjectUsage>;
  if (source === "all") {
    result = combined;
  } else if (source === "openrouter") {
    const or = sources.openrouter;
    if (!or || or.unavailable || !or.models) return {};
    return Object.fromEntries(
      Object.entries(or.models).map(([model, v]) => [
        model,
        { total_tokens: v.tokens, cost: v.cost, messages: v.requests, session_count: v.requests, by_source: ["openrouter"] },
      ]),
    );
  } else {
    result = {};
    const bySource = sources as unknown as Record<string, UsageSnapshot["sources"]["claude_code"] | undefined>;
    for (const key of snapshotKeys(sources, source)) {
      for (const [name, v] of Object.entries(bySource[key] ?? {})) {
        const prev = result[name];
        result[name] = prev
          ? {
              ...prev,
              total_tokens: prev.total_tokens + v.total_tokens,
              cost: prev.cost + v.cost,
              messages: prev.messages + v.messages,
              session_count: prev.session_count + v.session_count,
              by_source: [...prev.by_source, key],
            }
          : { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [key] };
      }
    }
  }

  if (!client) return result;
  return Object.fromEntries(Object.entries(result).filter(([path]) => clientOf(path, roots) === client));
}

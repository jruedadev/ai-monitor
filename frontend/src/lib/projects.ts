import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { clientOf, type ClientRoot } from "@/lib/clients";
import type { SourceKey } from "@/lib/sources";

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
    result = Object.fromEntries(
      Object.entries(sources[source]).map(([name, v]) => [
        name,
        { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [source] },
      ]),
    );
  }

  if (!client) return result;
  return Object.fromEntries(Object.entries(result).filter(([path]) => clientOf(path, roots) === client));
}

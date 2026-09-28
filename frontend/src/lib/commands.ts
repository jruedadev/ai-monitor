import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { clientOf, groupProjectsByClient } from "@/lib/clients";
import { formatDate } from "@/lib/format";
import { viewPath, type ViewKey } from "@/lib/routes";
import { collectSessions } from "@/lib/sessions";
import { SOURCE_META } from "@/lib/sources";
import { basename } from "@/lib/tree";

export const COMMAND_GROUPS = ["Vistas", "Clientes", "Proyectos", "Sesiones"] as const;

export interface CommandEntry {
  id: string;
  group: (typeof COMMAND_GROUPS)[number];
  label: string;
  hint?: string;
  to: string;
  keywords: string[];
}

const VIEWS: { view: ViewKey; label: string; keywords: string[] }[] = [
  { view: "home", label: "Inicio", keywords: ["briefing", "resumen"] },
  { view: "activity", label: "Actividad", keywords: ["tendencia", "sesiones", "días"] },
  { view: "spend", label: "Gasto", keywords: ["costo", "kpi"] },
  { view: "roi", label: "ROI", keywords: ["suscripción", "ahorro"] },
  { view: "projects", label: "Proyectos", keywords: ["clientes"] },
  { view: "settings", label: "Configuración", keywords: ["plan", "tarifa", "fuentes"] },
];

const MAX_SESSIONS = 500;

/** Índice del ⌘K sobre el snapshot en memoria (sin backend). */
export function buildCommandEntries(
  sources: UsageSnapshot["sources"] | null,
  combined: Record<string, ProjectUsage> | null,
): CommandEntry[] {
  const entries: CommandEntry[] = VIEWS.map((v) => ({
    id: `view:${v.view}`, group: "Vistas", label: v.label, to: viewPath(v.view), keywords: v.keywords,
  }));

  const paths = Object.keys(combined ?? {}).sort();
  for (const client of Object.keys(groupProjectsByClient(paths)).sort()) {
    entries.push({ id: `client:${client}`, group: "Clientes", label: client, to: viewPath("projects", client), keywords: [] });
  }
  for (const path of paths) {
    entries.push({
      id: `project:${path}`,
      group: "Proyectos",
      label: basename(path),
      hint: path,
      to: `${viewPath("projects", clientOf(path))}?proyecto=${encodeURIComponent(path)}`,
      keywords: [path, clientOf(path)],
    });
  }

  const sessions = collectSessions(sources, "all")
    .filter((s) => s.title && s.date)
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))
    .slice(0, MAX_SESSIONS);
  for (const s of sessions) {
    entries.push({
      id: `session:${s.source}:${s.session_id}`,
      group: "Sesiones",
      label: s.title as string,
      hint: `${SOURCE_META[s.source].label} · ${formatDate(s.date as string)}`,
      to: `/actividad?dia=${s.date}`,
      keywords: [s.project],
    });
  }
  return entries;
}

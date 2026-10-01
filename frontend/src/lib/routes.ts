/**
 * Estado de navegación ↔ URL. La URL es la única fuente de verdad: un enlace o una
 * recarga reproducen exactamente la misma vista.
 *
 *   /                        → Inicio (briefing)
 *   /actividad               → tendencia + sesiones del día
 *   /oficina                 → oficina pixel-art con las sesiones recientes
 *   /gasto, /gasto/roi       → Gasto y ROI
 *   /proyectos[/<cliente>]   → proyectos agrupados por cliente
 *   /recomendaciones         → recomendaciones del motor (?estado=aplicada|saltada|resuelta)
 *   /configuracion           → plan y estado de fuentes
 *   /bienvenida              → configuración inicial (fuera del layout con sidebar)
 *   ?fuente=<slug>           → filtro global de fuente (ausente = todas, sin OpenRouter)
 *   ?comparar=YYYY-MM        → mes comparado en el Inicio
 *   ?dia=YYYY-MM-DD          → día seleccionado en la tendencia / sesiones
 *   ?proyecto=<ruta>         → panel de detalle de proyecto abierto
 */
import type { SourceKey } from "@/lib/sources";

export const VIEW_KEYS = ["home", "activity", "spend", "roi", "projects", "recommendations", "settings", "onboarding", "office"] as const;
export type ViewKey = (typeof VIEW_KEYS)[number];

export const SOURCE_PARAM = "fuente";
export const COMPARE_PARAM = "comparar";
export const DAY_PARAM = "dia";
export const PROJECT_PARAM = "proyecto";
export const REC_STATUS_PARAM = "estado";

const VIEW_PATH: Record<ViewKey, string> = {
  home: "/",
  activity: "/actividad",
  spend: "/gasto",
  roi: "/gasto/roi",
  projects: "/proyectos",
  recommendations: "/recomendaciones",
  settings: "/configuracion",
  onboarding: "/bienvenida",
  office: "/oficina",
};

const SOURCE_SLUG: Record<Exclude<SourceKey, "all">, string> = {
  claude_code: "claude-code",
  codex: "codex",
  opencode: "opencode",
  hermes: "hermes",
  openrouter: "openrouter",
};

const SLUG_SOURCE = Object.fromEntries(
  Object.entries(SOURCE_SLUG).map(([key, slug]) => [slug, key as SourceKey]),
) as Record<string, SourceKey>;

export interface DashboardLocation {
  view: ViewKey;
  client: string | null;
}

/** Segmentos decodificados; null si la codificación está rota (%E0%A4%A). */
function segments(pathname: string): string[] | null {
  try {
    return pathname.split("/").filter(Boolean).map(decodeURIComponent);
  } catch {
    return null;
  }
}

/** null = ruta desconocida (el llamador redirige a "/"). */
export function parsePath(pathname: string): DashboardLocation | null {
  const parts = segments(pathname);
  if (!parts) return null;
  const [head, ...rest] = parts;
  if (parts.length === 0) return { view: "home", client: null };
  if (head === "actividad" && rest.length === 0) return { view: "activity", client: null };
  if (head === "gasto" && rest.length === 0) return { view: "spend", client: null };
  if (head === "gasto" && rest.length === 1 && rest[0] === "roi") return { view: "roi", client: null };
  if (head === "proyectos" && rest.length === 0) return { view: "projects", client: null };
  if (head === "proyectos" && rest.length === 1) return { view: "projects", client: rest[0] };
  if (head === "recomendaciones" && rest.length === 0) return { view: "recommendations", client: null };
  if (head === "configuracion" && rest.length === 0) return { view: "settings", client: null };
  if (head === "bienvenida" && rest.length === 0) return { view: "onboarding", client: null };
  if (head === "oficina" && rest.length === 0) return { view: "office", client: null };
  return null;
}

export function viewPath(view: ViewKey, client?: string | null): string {
  if (view === "projects" && client) return `/proyectos/${encodeURIComponent(client)}`;
  return VIEW_PATH[view];
}

export function parseSource(slug: string | null): SourceKey {
  return (slug && SLUG_SOURCE[slug]) || "all";
}

export function sourceSlug(source: SourceKey): string | null {
  return source === "all" ? null : SOURCE_SLUG[source];
}

export function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/** Enlace interno que conserva el filtro global ?fuente= de la URL actual. */
export function withSource(target: string, search: string): string {
  const current = new URLSearchParams(search).get(SOURCE_PARAM);
  const [path, query = ""] = target.split("?");
  const params = new URLSearchParams(query);
  if (current && !params.has(SOURCE_PARAM)) params.set(SOURCE_PARAM, current);
  return withQuery(path, params);
}

/** Query tras cambiar de fuente: el mes comparado y el día dependen de la fuente, se limpian. */
export function searchForSource(search: string, source: SourceKey): string {
  const params = new URLSearchParams(search);
  params.delete(COMPARE_PARAM);
  params.delete(DAY_PARAM);
  params.delete(SOURCE_PARAM);
  const slug = sourceSlug(source);
  if (slug) params.set(SOURCE_PARAM, slug);
  return params.toString();
}

/** Rutas de la estructura anterior (una ruta por fuente, /roi, /cliente/<X>). */
export function legacyRedirect(pathname: string, search: string): string | null {
  const parts = segments(pathname);
  if (!parts) return null;
  const params = new URLSearchParams(search);
  if (parts.length === 1 && SLUG_SOURCE[parts[0]]) {
    params.set(SOURCE_PARAM, parts[0]);
    return withQuery("/gasto", params);
  }
  if (parts.length === 1 && parts[0] === "roi") return withQuery("/gasto/roi", params);
  if (parts.length === 2 && parts[0] === "cliente") return withQuery(viewPath("projects", parts[1]), params);
  return null;
}

/** "ai-monitor:<esto>$" en la barra superior. */
export function promptPath(pathname: string): string {
  const parts = segments(pathname) ?? [];
  return parts.length === 0 ? "~" : `~/${parts.join("/")}`;
}

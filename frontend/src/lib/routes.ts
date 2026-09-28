/**
 * Estado de navegación del dashboard ↔ URL. La URL es la única fuente de verdad
 * de sección, cliente, día y proyecto: así un enlace o una recarga reproducen
 * exactamente la misma vista.
 *
 *   /                      → vista general ("Todo")
 *   /claude-code, /codex…  → una fuente
 *   /cliente/<cliente>     → vista general acotada a un cliente
 *   /roi                   → ROI
 *   ?dia=YYYY-MM-DD        → día seleccionado en la tendencia / sesiones
 *   ?proyecto=<ruta>       → panel de detalle de proyecto abierto
 */

export const SECTION_KEYS = ["all", "claude_code", "codex", "opencode", "hermes", "openrouter", "roi"] as const;
export type SectionKey = (typeof SECTION_KEYS)[number];

const SECTION_SLUG: Record<Exclude<SectionKey, "all">, string> = {
  claude_code: "claude-code",
  codex: "codex",
  opencode: "opencode",
  hermes: "hermes",
  openrouter: "openrouter",
  roi: "roi",
};

const SLUG_SECTION = Object.fromEntries(
  Object.entries(SECTION_SLUG).map(([key, slug]) => [slug, key as SectionKey]),
) as Record<string, SectionKey>;

export const DAY_PARAM = "dia";
export const PROJECT_PARAM = "proyecto";

export interface DashboardLocation {
  section: SectionKey;
  client: string | null;
}

/** null = ruta desconocida (el llamador redirige a "/"). */
export function parsePath(pathname: string): DashboardLocation | null {
  const parts = pathname.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts.length === 0) return { section: "all", client: null };
  if (parts[0] === "cliente" && parts.length === 2) return { section: "all", client: parts[1] };
  if (parts.length === 1 && SLUG_SECTION[parts[0]]) return { section: SLUG_SECTION[parts[0]], client: null };
  return null;
}

export function sectionPath(section: SectionKey): string {
  return section === "all" ? "/" : `/${SECTION_SLUG[section]}`;
}

export function clientPath(client: string): string {
  return `/cliente/${encodeURIComponent(client)}`;
}

export const SOURCE_PARAM = "fuente";
export const COMPARE_PARAM = "comparar";

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

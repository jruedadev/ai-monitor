/**
 * Cliente de un proyecto según raíces configurables (spec 2026-09-29 §2). Port de
 * clients.py; tests/fixtures/client_of_cases.json es el contrato compartido.
 */
export type ClientRootMode = "cliente" | "plano";

export interface ClientRoot {
  root: string;
  mode: ClientRootMode;
}

export const OTHER_CLIENT = "Otros";
export const MAX_CLIENT_ROOTS = 20;
export const DEFAULT_CLIENT_ROOTS: ClientRoot[] = [{ root: "DEV", mode: "cliente" }];

/** Índice del segmento que sigue a la raíz, o null. Ruta absoluta: prefijo por segmentos completos. */
function nextIndex(segments: string[], root: string): number | null {
  if (root.startsWith("/")) {
    const prefix = root.replace(/\/+$/, "").split("/");
    return prefix.every((part, i) => segments[i] === part) ? prefix.length : null;
  }
  const target = root.toUpperCase();
  const idx = segments.findIndex((s) => s.toUpperCase() === target);
  return idx === -1 ? null : idx + 1;
}

export function clientOf(projectPath: string, roots: ClientRoot[]): string {
  const segments = projectPath.split("/");
  for (const { root, mode } of roots) {
    const next = nextIndex(segments, root);
    if (next === null) continue;
    if (mode === "plano") return root.replace(/\/+$/, "").split("/").pop() || OTHER_CLIENT;
    return segments[next] || OTHER_CLIENT;
  }
  return OTHER_CLIENT;
}

export function groupProjectsByClient(paths: string[], roots: ClientRoot[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const path of paths) {
    (groups[clientOf(path, roots)] ??= []).push(path);
  }
  return groups;
}

/** Vista previa para el editor de raíces: ignora filas vacías (el usuario está escribiendo). */
export function previewClients(paths: string[], roots: ClientRoot[]): { clients: { name: string; count: number }[]; other: number } {
  const usable = roots.filter((r) => r.root.trim() !== "" && r.root.trim() !== "/");
  const groups = groupProjectsByClient(paths, usable);
  const other = groups[OTHER_CLIENT]?.length ?? 0;
  const clients = Object.entries(groups)
    .filter(([name]) => name !== OTHER_CLIENT)
    .map(([name, list]) => ({ name, count: list.length }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  return { clients, other };
}

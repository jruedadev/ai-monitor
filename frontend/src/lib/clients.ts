/**
 * Deriva el "cliente" de un path de proyecto según la convención
 * ~/DEV/<CLIENTE>/<proyecto>. Si el path no contiene un segmento "DEV",
 * el proyecto se agrupa bajo "Otros" en vez de romper la UI.
 */
export function clientOf(projectPath: string): string {
  const segments = projectPath.split("/");
  const idx = segments.findIndex((s) => s.toUpperCase() === "DEV");
  if (idx === -1 || idx + 1 >= segments.length) return "Otros";
  return segments[idx + 1];
}

export function groupProjectsByClient(paths: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const path of paths) {
    const client = clientOf(path);
    (groups[client] ??= []).push(path);
  }
  return groups;
}

/** Agrupa rutas de proyecto por su directorio padre inmediato, como haría
 * `tree` al listar una carpeta con sus subcarpetas. Sin dependencia de Node's
 * `path` (corre en el navegador). */
export function dirname(path: string): string {
  const idx = path.lastIndexOf("/");
  return idx <= 0 ? "/" : path.slice(0, idx);
}

export function basename(path: string): string {
  const idx = path.lastIndexOf("/");
  return idx === -1 || idx === path.length - 1 ? path : path.slice(idx + 1);
}

export interface GroupedEntry<T> {
  parent: string;
  entries: [string, T][];
  totalTokens: number;
}

export function groupByParentDir<T extends { total_tokens: number }>(
  rows: Record<string, T>,
): GroupedEntry<T>[] {
  const groups = new Map<string, [string, T][]>();
  for (const [path, value] of Object.entries(rows)) {
    const parent = dirname(path);
    if (!groups.has(parent)) groups.set(parent, []);
    groups.get(parent)!.push([path, value]);
  }

  return Array.from(groups.entries())
    .map(([parent, entries]) => ({
      parent,
      entries: entries.sort((a, b) => b[1].total_tokens - a[1].total_tokens),
      totalTokens: entries.reduce((s, [, v]) => s + v.total_tokens, 0),
    }))
    .sort((a, b) => b.totalTokens - a.totalTokens);
}

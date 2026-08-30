import { Sparkles, TerminalSquare, Code2, Network, type LucideIcon } from "lucide-react";

/**
 * Capa "componente" del design system: un único punto de verdad para la
 * identidad visual (color categórico + icono + label) de cada fuente,
 * consumido por Sidebar, KpiCards, ProjectTable y SessionDetail.
 */
export interface SourceMeta {
  label: string;
  color: string;
  icon: LucideIcon;
}

export const SOURCE_META: Record<string, SourceMeta> = {
  claude_code: { label: "Claude Code", color: "var(--viz-blue)", icon: Sparkles },
  codex: { label: "Codex", color: "var(--viz-violet)", icon: TerminalSquare },
  opencode: { label: "OpenCode", color: "var(--viz-aqua)", icon: Code2 },
  openrouter: { label: "OpenRouter", color: "var(--viz-orange)", icon: Network },
};

export function chipStyle(color: string | undefined) {
  return {
    color,
    backgroundColor: `color-mix(in srgb, ${color ?? "gray"} 15%, transparent)`,
  };
}

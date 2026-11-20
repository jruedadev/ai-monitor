import { Sparkles, TerminalSquare, Code2, Network, Bot, type LucideIcon } from "lucide-react";

/**
 * Capa "componente" del design system: un único punto de verdad para la
 * identidad visual (color categórico + icono + label) de cada fuente,
 * consumido por Sidebar, SourceChip, SessionDetail y RoiView.
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
  hermes: { label: "Hermes", color: "var(--viz-yellow)", icon: Bot },
  openrouter: { label: "OpenRouter", color: "var(--viz-orange)", icon: Network },
};

/** Filtro global de fuente (?fuente=). "all" suma las cuatro fuentes por proyecto; nunca OpenRouter. */
export const SOURCE_KEYS = ["all", "claude_code", "codex", "opencode", "hermes", "openrouter"] as const;
export type SourceKey = (typeof SOURCE_KEYS)[number] | `claude_code@${string}`;

/** Fuente de una cuenta no default de Claude Code: `claude_code@<id>` (forma de la API). */
export function isAccountSource(source: string): source is `claude_code@${string}` {
  return /^claude_code@.+$/.test(source);
}

/** El briefing enlaza con `claude-code@<id>` (slug de URL); la API habla `claude_code@<id>`. */
export function normalizeFuente(value: string): string {
  return value.startsWith("claude-code@") ? `claude_code@${value.slice("claude-code@".length)}` : value;
}

/** Identidad visual de una fuente; una cuenta de Claude Code usa la de Claude Code. */
export function sourceMeta(source: string): SourceMeta {
  return SOURCE_META[isAccountSource(source) ? "claude_code" : source];
}

/** El snapshot en vivo agrupa todas las cuentas de Claude Code bajo `claude_code`. */
export function snapshotSource(source: Exclude<SourceKey, "all">): Exclude<SourceKey, "all" | `claude_code@${string}`> {
  return isAccountSource(source) ? "claude_code" : source;
}

export function accountSourceLabel(label: string): string {
  return `${label} (Claude Code)`;
}

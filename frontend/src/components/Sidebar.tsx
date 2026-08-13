const SECTIONS = [
  { key: "all", label: "Todo" },
  { key: "claude_code", label: "Claude Code" },
  { key: "codex", label: "Codex" },
  { key: "opencode", label: "OpenCode" },
  { key: "openrouter", label: "OpenRouter" },
] as const;

export type SectionKey = (typeof SECTIONS)[number]["key"];

interface SidebarProps {
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
}

export function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <nav className="w-48 shrink-0 border-r p-4 space-y-1">
      {SECTIONS.map((s) => (
        <button
          key={s.key}
          onClick={() => onSelect(s.key)}
          className={`block w-full text-left rounded px-3 py-2 text-sm ${
            active === s.key ? "bg-accent text-accent-foreground" : "hover:bg-muted"
          }`}
        >
          {s.label}
        </button>
      ))}
    </nav>
  );
}

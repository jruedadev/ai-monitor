import { LayoutGrid, Activity } from "lucide-react";
import { SOURCE_META } from "@/lib/sources";

const SECTIONS = [
  { key: "all", label: "Todo", icon: LayoutGrid, color: undefined },
  { key: "claude_code", ...SOURCE_META.claude_code },
  { key: "codex", ...SOURCE_META.codex },
  { key: "opencode", ...SOURCE_META.opencode },
  { key: "openrouter", ...SOURCE_META.openrouter },
] as const;

export type SectionKey = (typeof SECTIONS)[number]["key"];

interface SidebarProps {
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
}

export function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <nav className="w-56 shrink-0 border-r bg-sidebar flex flex-col">
      <div className="flex items-center gap-2 px-5 h-16 border-b">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Activity className="h-4 w-4" />
        </div>
        <span className="font-semibold tracking-tight">ai-monitor</span>
      </div>
      <div className="flex-1 p-3 space-y-1">
        {SECTIONS.map((s) => {
          const Icon = s.icon;
          const isActive = active === s.key;
          return (
            <button
              key={s.key}
              onClick={() => onSelect(s.key)}
              className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                isActive
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" style={{ color: isActive ? s.color : undefined }} />
              {s.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

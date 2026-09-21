import { useState } from "react";
import { LayoutGrid, Activity, Scale, ChevronRight, FolderKanban } from "lucide-react";
import { SOURCE_META } from "@/lib/sources";

const TOOL_SECTIONS = [
  { key: "all", label: "Todo", icon: LayoutGrid, color: undefined },
  { key: "claude_code", ...SOURCE_META.claude_code },
  { key: "codex", ...SOURCE_META.codex },
  { key: "opencode", ...SOURCE_META.opencode },
  { key: "hermes", ...SOURCE_META.hermes },
  { key: "openrouter", ...SOURCE_META.openrouter },
] as const;

const ROI_ITEM = { key: "roi", label: "ROI", icon: Scale, color: "var(--viz-aqua)" } as const;

export type SectionKey = (typeof TOOL_SECTIONS)[number]["key"] | typeof ROI_ITEM.key;

interface SidebarProps {
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
  projectsByClient: Record<string, string[]>;
  activeClient: string | null;
  onSelectClient: (client: string | null) => void;
  onSelectProject: (path: string) => void;
}

function basename(path: string): string {
  return path.split("/").filter(Boolean).pop() ?? path;
}

const navButtonClass = (isActive: boolean) =>
  `group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
    isActive
      ? "bg-accent text-accent-foreground font-medium"
      : "text-muted-foreground hover:bg-muted hover:text-foreground"
  }`;

export function Sidebar({
  active, onSelect, projectsByClient, activeClient, onSelectClient, onSelectProject,
}: SidebarProps) {
  const [expandedClient, setExpandedClient] = useState<string | null>(null);
  const clients = Object.keys(projectsByClient).sort();

  const handleSelectClient = (client: string) => {
    setExpandedClient((prev) => (prev === client ? null : client));
    onSelectClient(client);
  };

  return (
    <nav className="w-56 shrink-0 border-r bg-sidebar flex flex-col overflow-y-auto">
      <div className="flex items-center gap-2 px-5 h-16 border-b">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Activity className="h-4 w-4" />
        </div>
        <span className="font-semibold tracking-tight">ai-monitor</span>
      </div>
      <div className="flex-1 p-3 space-y-4">
        <div className="space-y-1">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Herramientas
          </p>
          {TOOL_SECTIONS.map((s) => {
            const Icon = s.icon;
            const isActive = active === s.key && !activeClient;
            return (
              <button
                key={s.key}
                onClick={() => { onSelect(s.key); onSelectClient(null); }}
                className={navButtonClass(isActive)}
              >
                <Icon className="h-4 w-4 shrink-0" style={{ color: isActive ? s.color : undefined }} />
                {s.label}
              </button>
            );
          })}
        </div>

        <div className="space-y-1">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Proyectos
          </p>
          {clients.length === 0 ? (
            <p className="px-3 text-xs text-muted-foreground">Sin proyectos</p>
          ) : (
            clients.map((client) => {
              const isActive = activeClient === client;
              const isExpanded = expandedClient === client;
              return (
                <div key={client}>
                  <button
                    onClick={() => handleSelectClient(client)}
                    className={navButtonClass(isActive) + " gap-2"}
                  >
                    <ChevronRight
                      className={`h-3.5 w-3.5 shrink-0 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                    />
                    <FolderKanban className="h-4 w-4 shrink-0" />
                    <span className="truncate">{client}</span>
                  </button>
                  {isExpanded && (
                    <div className="ml-6 border-l pl-2 space-y-0.5 py-1">
                      {projectsByClient[client].map((path) => (
                        <button
                          key={path}
                          onClick={() => onSelectProject(path)}
                          className="block w-full truncate rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                          title={path}
                        >
                          {basename(path)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="space-y-1">
          <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            ROI
          </p>
          <button
            onClick={() => { onSelect(ROI_ITEM.key); onSelectClient(null); }}
            className={navButtonClass(active === ROI_ITEM.key)}
          >
            <ROI_ITEM.icon
              className="h-4 w-4 shrink-0"
              style={{ color: active === ROI_ITEM.key ? ROI_ITEM.color : undefined }}
            />
            {ROI_ITEM.label}
          </button>
        </div>
      </div>
    </nav>
  );
}

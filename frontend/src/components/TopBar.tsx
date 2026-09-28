import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Search } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ThemeToggle } from "@/components/ThemeToggle";
import { CommandPalette } from "@/components/CommandPalette";
import { SourceFilter } from "@/components/SourceFilter";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { promptPath } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";

interface TopBarProps {
  connected: boolean;
  source: SourceKey;
  onSourceChange: (source: SourceKey) => void;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
}

export function TopBar({ connected, source, onSourceChange, sources, combined }: TopBarProps) {
  const { pathname } = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur md:gap-3 md:px-6">
      <SidebarTrigger className="-ml-1" />
      <p className="hidden min-w-0 truncate font-mono text-sm text-muted-foreground sm:block">
        <span className="text-link">ai-monitor</span>:{promptPath(pathname)}$
      </p>
      <div className="ml-auto flex shrink-0 items-center gap-2">
        <SourceFilter value={source} onChange={onSourceChange} />
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          aria-label="Buscar"
          aria-keyshortcuts="Meta+K Control+K"
          className="inline-flex h-8 items-center gap-2 rounded-lg border px-2 text-sm text-muted-foreground hover:text-foreground md:px-3"
        >
          <Search className="h-4 w-4" aria-hidden />
          <span className="hidden md:inline">Buscar</span>
          <kbd className="hidden rounded border bg-muted px-1.5 font-mono text-[10px] md:inline">⌘K</kbd>
        </button>
        <span
          role="status"
          aria-live="polite"
          className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${
            connected ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground"
          }`}
        >
          <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"}`} />
          <span className="sr-only md:not-sr-only">{connected ? "En vivo" : "Conectando…"}</span>
        </span>
        <ThemeToggle />
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} sources={sources} combined={combined} />
    </header>
  );
}

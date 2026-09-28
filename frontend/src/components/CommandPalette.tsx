import { useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@/components/ui/command";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { COMMAND_GROUPS, buildCommandEntries, type CommandEntry } from "@/lib/commands";
import { withSource } from "@/lib/routes";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
}

export function CommandPalette({ open, onOpenChange, sources, combined }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { search } = useLocation();
  const entries = useMemo(() => buildCommandEntries(sources, combined), [sources, combined]);

  const go = (entry: CommandEntry) => {
    onOpenChange(false);
    navigate(entry.keepSource === false ? entry.to : withSource(entry.to, search));
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title="Buscar" description="Vistas, clientes, proyectos y sesiones">
      <CommandInput placeholder="Buscar vistas, clientes, proyectos o sesiones…" />
      <CommandList>
        <CommandEmpty>Sin resultados.</CommandEmpty>
        {COMMAND_GROUPS.map((group) => {
          const items = entries.filter((e) => e.group === group);
          if (items.length === 0) return null;
          return (
            <CommandGroup key={group} heading={group}>
              {items.map((e) => (
                <CommandItem key={e.id} value={`${e.label} ${e.keywords.join(" ")} ${e.id}`} onSelect={() => go(e)}>
                  <span className="truncate">{e.label}</span>
                  {e.hint && <span className="ml-auto truncate pl-3 font-mono text-xs text-muted-foreground">{e.hint}</span>}
                </CommandItem>
              ))}
            </CommandGroup>
          );
        })}
      </CommandList>
    </CommandDialog>
  );
}

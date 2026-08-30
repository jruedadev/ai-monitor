import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { SOURCE_META, chipStyle } from "@/lib/sources";
import type { ProjectUsage } from "@/lib/api";

interface ProjectTableProps {
  projects: Record<string, ProjectUsage>;
  onSelectProject?: (project: string) => void;
}

export function ProjectTable({ projects, onSelectProject }: ProjectTableProps) {
  const rows = Object.entries(projects).sort((a, b) => b[1].total_tokens - a[1].total_tokens);
  const maxTokens = Math.max(1, ...rows.map(([, v]) => v.total_tokens));

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-5 py-4 border-b">
        <h2 className="font-semibold">Proyectos</h2>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Proyecto</TableHead>
            <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Fuente</TableHead>
            <TableHead className="text-right text-xs uppercase tracking-wide text-muted-foreground">Tokens</TableHead>
            <TableHead className="text-right text-xs uppercase tracking-wide text-muted-foreground">Costo</TableHead>
            <TableHead className="text-right text-xs uppercase tracking-wide text-muted-foreground">Sesiones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map(([name, v]) => (
            <TableRow
              key={name}
              className={onSelectProject ? "cursor-pointer" : undefined}
              onClick={onSelectProject ? () => onSelectProject(name) : undefined}
            >
              <TableCell className="max-w-xs">
                <div className={`truncate font-medium ${onSelectProject ? "hover:underline underline-offset-2" : ""}`} title={name}>{name}</div>
                <div className="mt-1.5 h-1 w-full max-w-[180px] rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.max(4, (v.total_tokens / maxTokens) * 100)}%`,
                      backgroundColor: "var(--viz-blue)",
                    }}
                  />
                </div>
              </TableCell>
              <TableCell>
                <div className="flex gap-1.5">
                  {v.by_source.map((src) => {
                    const meta = SOURCE_META[src];
                    return (
                      <span
                        key={src}
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                        style={chipStyle(meta?.color)}
                      >
                        {meta?.label ?? src}
                      </span>
                    );
                  })}
                </div>
              </TableCell>
              <TableCell className="text-right tabular-nums">{v.total_tokens.toLocaleString("es")}</TableCell>
              <TableCell className="text-right tabular-nums">${v.cost.toFixed(2)}</TableCell>
              <TableCell className="text-right tabular-nums">{v.session_count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

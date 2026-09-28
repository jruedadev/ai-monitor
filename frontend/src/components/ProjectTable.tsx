import { Fragment } from "react";
import { Folder } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { SourceChip } from "@/components/SourceChip";
import { formatInt, formatUsd } from "@/lib/format";
import { groupByParentDir, basename } from "@/lib/tree";
import type { ProjectUsage } from "@/lib/api";

interface ProjectTableProps {
  projects: Record<string, ProjectUsage>;
  onSelectProject?: (project: string) => void;
}

export function ProjectTable({ projects, onSelectProject }: ProjectTableProps) {
  const groups = groupByParentDir(projects);
  const maxTokens = Math.max(1, ...Object.values(projects).map((v) => v.total_tokens));

  return (
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
        {groups.map(({ parent, entries }) => (
          <Fragment key={parent}>
            <TableRow key={`group-${parent}`} className="hover:bg-transparent bg-muted/40">
              <TableCell colSpan={5} className="py-1.5">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
                  <Folder className="h-3.5 w-3.5" aria-hidden />
                  <span className="truncate" title={parent}>{parent}</span>
                </div>
              </TableCell>
            </TableRow>
            {entries.map(([name, v]) => (
              <TableRow key={name}>
                <TableCell className="max-w-xs pl-8">
                  {onSelectProject ? (
                    <button
                      type="button"
                      onClick={() => onSelectProject(name)}
                      className="block max-w-full truncate rounded-sm text-left font-medium cursor-pointer hover:underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                      title={name}
                    >
                      {basename(name)}
                    </button>
                  ) : (
                    <div className="truncate font-medium" title={name}>{basename(name)}</div>
                  )}
                  {/* Magnitud relativa en tinta neutra: el azul es la identidad de Claude Code. */}
                  <div aria-hidden className="mt-1.5 h-1 w-full max-w-[180px] rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-muted-foreground/60"
                      style={{ width: `${Math.max(4, (v.total_tokens / maxTokens) * 100)}%` }}
                    />
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1.5">
                    {v.by_source.map((src) => <SourceChip key={src} source={src} />)}
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatInt(v.total_tokens)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatUsd(v.cost)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatInt(v.session_count)}</TableCell>
              </TableRow>
            ))}
          </Fragment>
        ))}
      </TableBody>
    </Table>
  );
}

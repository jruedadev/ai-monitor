import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { ProjectUsage } from "@/lib/api";

interface ProjectTableProps {
  projects: Record<string, ProjectUsage>;
}

export function ProjectTable({ projects }: ProjectTableProps) {
  const rows = Object.entries(projects).sort((a, b) => b[1].total_tokens - a[1].total_tokens);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Proyecto</TableHead>
          <TableHead className="text-right">Tokens</TableHead>
          <TableHead className="text-right">Costo</TableHead>
          <TableHead className="text-right">Sesiones</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(([name, v]) => (
          <TableRow key={name}>
            <TableCell className="max-w-xs truncate" title={name}>{name}</TableCell>
            <TableCell className="text-right">{v.total_tokens.toLocaleString()}</TableCell>
            <TableCell className="text-right">${v.cost.toFixed(2)}</TableCell>
            <TableCell className="text-right">{v.session_count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

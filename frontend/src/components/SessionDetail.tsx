import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, Title } from "@tremor/react";
import type { SectionKey } from "@/components/Sidebar";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";

const SOURCE_LABELS: Record<string, string> = {
  claude_code: "Claude Code",
  codex: "Codex",
  opencode: "OpenCode",
};

interface FlatSession extends SessionDetailEntry {
  source: string;
  project: string;
}

interface SessionDetailProps {
  sources: UsageSnapshot["sources"] | null | undefined;
  section: SectionKey;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
}

function collectSessions(sources: UsageSnapshot["sources"] | null | undefined, section: SectionKey): FlatSession[] {
  if (!sources) return [];
  const sourceKeys = section === "all"
    ? (["claude_code", "codex", "opencode"] as const)
    : section === "openrouter" ? [] : ([section] as const);

  const rows: FlatSession[] = [];
  for (const key of sourceKeys) {
    for (const [project, usage] of Object.entries(sources[key] ?? {})) {
      for (const session of usage.sessions_detail) {
        rows.push({ ...session, source: key, project });
      }
    }
  }
  return rows;
}

export function SessionDetail({ sources, section, selectedDate, onSelectDate }: SessionDetailProps) {
  if (section === "openrouter") {
    return null;
  }

  const allSessions = collectSessions(sources, section);
  const availableDates = Array.from(new Set([
    ...allSessions.map((s) => s.date).filter((d): d is string => !!d),
    ...(selectedDate ? [selectedDate] : []),
  ])).sort((a, b) => b.localeCompare(a));

  const rows = (selectedDate ? allSessions.filter((s) => s.date === selectedDate) : allSessions)
    .sort((a, b) => b.tokens - a.tokens);

  return (
    <Card>
      <div className="flex items-center justify-between gap-4 mb-4">
        <Title>Sesiones por fecha</Title>
        <select
          className="text-sm border rounded px-2 py-1 bg-background"
          value={selectedDate ?? ""}
          onChange={(e) => onSelectDate(e.target.value || null)}
        >
          <option value="">Todas las fechas ({allSessions.length})</option>
          {availableDates.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {selectedDate ? `Sin sesiones para ${selectedDate}.` : "Sin sesiones registradas."}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              {section === "all" && <TableHead>Herramienta</TableHead>}
              <TableHead>Proyecto</TableHead>
              <TableHead>Sesión</TableHead>
              <TableHead className="text-right">Tokens</TableHead>
              <TableHead className="text-right">Costo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((s) => (
              <TableRow key={`${s.source}-${s.session_id}`}>
                {section === "all" && <TableCell>{SOURCE_LABELS[s.source]}</TableCell>}
                <TableCell className="max-w-xs truncate" title={s.project}>{s.project}</TableCell>
                <TableCell className="max-w-sm truncate" title={s.title ?? s.session_id}>
                  {s.title ?? s.session_id}
                </TableCell>
                <TableCell className="text-right">{s.tokens.toLocaleString()}</TableCell>
                <TableCell className="text-right">${s.cost.toFixed(2)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

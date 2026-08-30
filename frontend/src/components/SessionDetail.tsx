import { CalendarClock } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { SectionKey } from "@/components/Sidebar";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";

const SOURCE_STYLE: Record<string, { label: string; color: string }> = {
  claude_code: { label: "Claude Code", color: "var(--viz-blue)" },
  codex: { label: "Codex", color: "var(--viz-violet)" },
  opencode: { label: "OpenCode", color: "var(--viz-aqua)" },
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
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="flex items-center justify-between gap-4 px-5 py-4 border-b">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-muted-foreground" />
          <h2 className="font-semibold">Sesiones por fecha</h2>
        </div>
        <select
          className="text-sm border rounded-md px-2 py-1.5 bg-background"
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
        <p className="px-5 py-8 text-center text-sm text-muted-foreground">
          {selectedDate ? `Sin sesiones para ${selectedDate}.` : "Sin sesiones registradas."}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {section === "all" && <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Herramienta</TableHead>}
              <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Proyecto</TableHead>
              <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Sesión</TableHead>
              <TableHead className="text-right text-xs uppercase tracking-wide text-muted-foreground">Tokens</TableHead>
              <TableHead className="text-right text-xs uppercase tracking-wide text-muted-foreground">Costo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((s) => {
              const style = SOURCE_STYLE[s.source];
              return (
                <TableRow key={`${s.source}-${s.session_id}`}>
                  {section === "all" && (
                    <TableCell>
                      <span
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{
                          color: style?.color,
                          backgroundColor: `color-mix(in srgb, ${style?.color ?? "gray"} 15%, transparent)`,
                        }}
                      >
                        {style?.label ?? s.source}
                      </span>
                    </TableCell>
                  )}
                  <TableCell className="max-w-xs truncate" title={s.project}>{s.project}</TableCell>
                  <TableCell className="max-w-sm truncate" title={s.title ?? s.session_id}>
                    {s.title ?? s.session_id}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{s.tokens.toLocaleString("es")}</TableCell>
                  <TableCell className="text-right tabular-nums">${s.cost.toFixed(2)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

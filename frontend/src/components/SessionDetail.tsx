import { Fragment } from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { SOURCE_META } from "@/lib/sources";
import { collectSessions, SESSION_SOURCES, type FlatSession } from "@/lib/sessions";
import { SessionIdentity } from "@/components/SessionIdentity";
import type { SectionKey } from "@/components/Sidebar";
import type { UsageSnapshot } from "@/lib/api";

interface SessionDetailProps {
  sources: UsageSnapshot["sources"] | null | undefined;
  section: SectionKey;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onSelectProject?: (project: string) => void;
}

function groupBySource(rows: FlatSession[]) {
  return SESSION_SOURCES
    .map((source) => ({ source, rows: rows.filter((r) => r.source === source).sort((a, b) => b.tokens - a.tokens) }))
    .filter((g) => g.rows.length > 0);
}

export function SessionDetail({ sources, section, selectedDate, onSelectDate, onSelectProject }: SessionDetailProps) {
  if (section === "openrouter") {
    return null;
  }

  const allSessions = collectSessions(sources, section);
  const availableDates = Array.from(new Set([
    ...allSessions.map((s) => s.date).filter((d): d is string => !!d),
    ...(selectedDate ? [selectedDate] : []),
  ])).sort((a, b) => b.localeCompare(a));

  const filtered = selectedDate ? allSessions.filter((s) => s.date === selectedDate) : allSessions;
  const groups = section === "all" ? groupBySource(filtered) : [{ source: section, rows: filtered.sort((a, b) => b.tokens - a.tokens) }];

  return (
    <div>
      <div className="flex items-center justify-end gap-4 mb-4">
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
      {filtered.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {selectedDate ? `Sin sesiones para ${selectedDate}.` : "Sin sesiones registradas."}
        </p>
      ) : (
        <div className="space-y-6">
          {groups.map(({ source, rows }) => {
            const meta = SOURCE_META[source];
            const Icon = meta?.icon;
            return (
              <Fragment key={source}>
                <div className="flex items-center gap-2 mb-2">
                  {Icon && <Icon className="h-4 w-4" style={{ color: meta.color }} />}
                  <h3 className="text-sm font-semibold">{meta?.label ?? source}</h3>
                  <span className="text-xs text-muted-foreground">({rows.length})</span>
                </div>
                <div className="rounded-xl border bg-card overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Proyecto</TableHead>
                        <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Sesión</TableHead>
                        <TableHead className="text-right text-xs uppercase tracking-wide text-muted-foreground">Tokens</TableHead>
                        <TableHead className="text-right text-xs uppercase tracking-wide text-muted-foreground">Costo</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((s) => (
                        <TableRow key={`${s.source}-${s.session_id}`}>
                          <TableCell className="max-w-xs">
                            {onSelectProject ? (
                              <button
                                className="truncate text-left hover:underline underline-offset-2"
                                title={s.project}
                                onClick={() => onSelectProject(s.project)}
                              >
                                {s.project}
                              </button>
                            ) : (
                              <div className="truncate" title={s.project}>{s.project}</div>
                            )}
                          </TableCell>
                          <TableCell className="max-w-sm">
                            <SessionIdentity title={s.title} sessionId={s.session_id} />
                          </TableCell>
                          <TableCell className="text-right tabular-nums">{s.tokens.toLocaleString("es")}</TableCell>
                          <TableCell className="text-right tabular-nums">${s.cost.toFixed(2)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}

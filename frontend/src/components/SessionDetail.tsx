import { CalendarClock } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { SOURCE_META, chipStyle } from "@/lib/sources";
import { collectSessions } from "@/lib/sessions";
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

export function SessionDetail({ sources, section, selectedDate, onSelectDate, onSelectProject }: SessionDetailProps) {
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
              const meta = SOURCE_META[s.source];
              return (
                <TableRow key={`${s.source}-${s.session_id}`}>
                  {section === "all" && (
                    <TableCell>
                      <span
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                        style={chipStyle(meta?.color)}
                      >
                        {meta?.label ?? s.source}
                      </span>
                    </TableCell>
                  )}
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
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

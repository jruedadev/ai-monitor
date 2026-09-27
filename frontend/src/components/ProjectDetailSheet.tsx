import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { SourceChip } from "@/components/SourceChip";
import { formatCompact, formatInt, formatUsd } from "@/lib/format";
import { collectSessions } from "@/lib/sessions";
import { SessionIdentity } from "@/components/SessionIdentity";
import type { SectionKey } from "@/lib/routes";
import type { UsageSnapshot } from "@/lib/api";

interface ProjectDetailSheetProps {
  sources: UsageSnapshot["sources"] | null | undefined;
  section: SectionKey;
  project: string | null;
  onClose: () => void;
}

export function ProjectDetailSheet({ sources, section, project, onClose }: ProjectDetailSheetProps) {
  const sessions = project
    ? collectSessions(sources, section, project).sort((a, b) => {
      const ta = typeof a.last_ts === "string" ? a.last_ts : String(a.last_ts ?? "");
      const tb = typeof b.last_ts === "string" ? b.last_ts : String(b.last_ts ?? "");
      return tb.localeCompare(ta);
    })
    : [];

  const totalTokens = sessions.reduce((s, r) => s + r.tokens, 0);
  const totalCost = sessions.reduce((s, r) => s + r.cost, 0);
  const usedSources = Array.from(new Set(sessions.map((s) => s.source)));

  return (
    <Sheet open={!!project} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full data-[side=right]:sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="break-all">{project}</SheetTitle>
          <SheetDescription>Detalle de sesiones para este proyecto</SheetDescription>
        </SheetHeader>

        <div className="px-4 flex flex-wrap gap-2">
          {usedSources.map((src) => <SourceChip key={src} source={src} />)}
        </div>

        <div className="px-4 grid grid-cols-3 gap-3">
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Tokens</p>
            <p className="text-lg font-semibold tabular-nums">{formatInt(totalTokens)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Costo</p>
            <p className="text-lg font-semibold tabular-nums">{formatUsd(totalCost)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Sesiones</p>
            <p className="text-lg font-semibold tabular-nums">{formatInt(sessions.length)}</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {sessions.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Sin sesiones registradas.</p>
          ) : (
            <Table className="table-fixed w-full">
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  {section === "all" && <TableHead className="w-[92px] text-xs uppercase tracking-wide text-muted-foreground">Fuente</TableHead>}
                  <TableHead className="w-[76px] text-xs uppercase tracking-wide text-muted-foreground">Fecha</TableHead>
                  <TableHead className="text-xs uppercase tracking-wide text-muted-foreground">Sesión</TableHead>
                  <TableHead className="w-[76px] text-right text-xs uppercase tracking-wide text-muted-foreground">Tokens</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((s) => (
                  <TableRow key={`${s.source}-${s.session_id}`}>
                    {section === "all" && (
                      <TableCell className="overflow-hidden">
                        <SourceChip source={s.source} />
                      </TableCell>
                    )}
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{s.date ?? "—"}</TableCell>
                    <TableCell className="overflow-hidden">
                      <SessionIdentity title={s.title} sessionId={s.session_id} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums whitespace-nowrap overflow-hidden">{formatCompact(s.tokens)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

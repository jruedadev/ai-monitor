import { FolderGit2, Coins, DollarSign, MessagesSquare } from "lucide-react";
import type { ComponentType } from "react";
import type { ProjectUsage } from "@/lib/api";
import { formatInt, formatUsd } from "@/lib/format";

interface KpiCardsProps {
  projects: Record<string, ProjectUsage>;
}

interface Stat {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}

export function KpiCards({ projects }: KpiCardsProps) {
  const rows = Object.values(projects);
  const totalTokens = rows.reduce((s, r) => s + r.total_tokens, 0);
  const totalCost = rows.reduce((s, r) => s + r.cost, 0);
  const totalSessions = rows.reduce((s, r) => s + r.session_count, 0);

  // Íconos en tinta neutra: los colores --viz-* identifican fuentes, y una
  // métrica agregada no es ninguna fuente.
  const stats: Stat[] = [
    { label: "Proyectos", value: formatInt(rows.length), icon: FolderGit2 },
    { label: "Tokens totales", value: formatInt(totalTokens), icon: Coins },
    { label: "Costo estimado", value: formatUsd(totalCost), icon: DollarSign },
    { label: "Sesiones", value: formatInt(totalSessions), icon: MessagesSquare },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map(({ label, value, icon: Icon }) => (
        <div
          key={label}
          className="rounded-xl border bg-card p-5 flex items-start gap-4"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
            <Icon className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-semibold tracking-tight tabular-nums truncate">{value}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

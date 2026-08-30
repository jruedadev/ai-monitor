import { FolderGit2, Coins, DollarSign, MessagesSquare } from "lucide-react";
import type { ComponentType, CSSProperties } from "react";
import type { ProjectUsage } from "@/lib/api";

interface KpiCardsProps {
  projects: Record<string, ProjectUsage>;
}

interface Stat {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string; style?: CSSProperties }>;
  color: string;
}

export function KpiCards({ projects }: KpiCardsProps) {
  const rows = Object.values(projects);
  const totalTokens = rows.reduce((s, r) => s + r.total_tokens, 0);
  const totalCost = rows.reduce((s, r) => s + r.cost, 0);
  const totalSessions = rows.reduce((s, r) => s + r.session_count, 0);

  const stats: Stat[] = [
    { label: "Proyectos", value: rows.length.toLocaleString("es"), icon: FolderGit2, color: "var(--viz-blue)" },
    { label: "Tokens totales", value: totalTokens.toLocaleString("es"), icon: Coins, color: "var(--viz-orange)" },
    { label: "Costo estimado", value: `$${totalCost.toFixed(2)}`, icon: DollarSign, color: "var(--viz-aqua)" },
    { label: "Sesiones", value: totalSessions.toLocaleString("es"), icon: MessagesSquare, color: "var(--viz-yellow)" },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map(({ label, value, icon: Icon, color }) => (
        <div
          key={label}
          className="rounded-xl border bg-card p-5 flex items-start gap-4 transition-shadow hover:shadow-md"
        >
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)` }}
          >
            <Icon className="h-5 w-5" style={{ color }} />
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

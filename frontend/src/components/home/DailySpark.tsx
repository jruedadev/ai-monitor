import { Link } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import { useHistory } from "@/hooks/useHistory";
import { dailyCostSeries } from "@/lib/briefing";
import { formatDayShort, formatUsd } from "@/lib/format";
import { withSource } from "@/lib/routes";
import { SOURCE_META, type SourceKey } from "@/lib/sources";

const HISTORY_DAYS = 62;

interface DailySparkProps {
  source: SourceKey;
  from: string;
  to: string;
  search: string;
}

export function DailySpark({ source, from, to, search }: DailySparkProps) {
  const history = useHistory(HISTORY_DAYS);
  const points = history.status === "ready" ? dailyCostSeries(history.data, source, from, to) : [];
  const max = points.reduce((m, p) => Math.max(m, p.cost), 0);
  // Identidad de la fuente filtrada; tinta neutra en "Todas" (el cyan nunca va en datos).
  const color = source === "all" ? "var(--muted-foreground)" : SOURCE_META[source].color;

  return (
    <section aria-labelledby="spark-title" className="rounded-xl border bg-card p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="spark-title" className="text-sm font-medium">Gasto diario del mes</h2>
        <Link to={withSource("/actividad", search)} className="text-sm text-link underline-offset-4 hover:underline">
          Ver actividad
        </Link>
      </div>
      {history.status === "loading" && <Skeleton className="mt-4 h-32 w-full" />}
      {history.status === "error" && (
        <p role="alert" className="mt-4 text-sm text-muted-foreground">No se pudo cargar el historial ({history.message}).</p>
      )}
      {history.status === "ready" && (
        <svg
          viewBox={`0 0 ${Math.max(points.length, 1) * 10} 100`}
          preserveAspectRatio="none"
          className="mt-4 h-32 w-full"
          role="img"
          aria-label={`Gasto diario del ${formatDayShort(from)} al ${formatDayShort(to)}; máximo ${formatUsd(max)}`}
        >
          {points.map((p, i) => {
            const height = max > 0 ? (p.cost / max) * 96 : 0;
            return (
              <rect key={p.date} x={i * 10 + 1} y={100 - height} width={8} height={height} rx={1.5} fill={color}>
                <title>{`${formatDayShort(p.date)}: ${formatUsd(p.cost)}`}</title>
              </rect>
            );
          })}
        </svg>
      )}
    </section>
  );
}

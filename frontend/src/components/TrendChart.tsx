import { useRef, type CSSProperties } from "react";
import type { CustomTooltipProps } from "@tremor/react";
import { LineChart } from "@tremor/react";
import { AlertCircle, MousePointerClick, RotateCw, X } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useHistory } from "@/hooks/useHistory";
import { useClientRoots } from "@/hooks/appSettingsContext";
import { SOURCE_META } from "@/lib/sources";
import { clientOf, type ClientRoot } from "@/lib/clients";
import { formatCompact, formatDate, formatDayShort } from "@/lib/format";
import type { HistoryResponse } from "@/lib/api";
import type { SourceKey } from "@/lib/sources";

const HISTORY_DAYS = 90;

interface TrendChartProps {
  section: SourceKey;
  clientFilter?: string | null;
  selectedDate?: string | null;
  onSelectDate?: (date: string | null) => void;
}

interface ChartPoint {
  /** ISO YYYY-MM-DD: lo que viaja a onSelectDate. */
  date: string;
  /** Etiqueta del eje/tooltip ("18 jul"). */
  label: string;
  Tokens: number;
}

function buildSeries(data: HistoryResponse, section: SourceKey, clientFilter: string | null | undefined, roots: ClientRoot[]): ChartPoint[] {
  const byDate: Record<string, number> = {};
  if (section === "openrouter") {
    for (const row of data.daily_model) {
      if (row.model !== "__all__") continue;
      const date = row.date.slice(0, 10);
      byDate[date] = (byDate[date] ?? 0) + row.tokens;
    }
  } else {
    for (const row of data.daily_project) {
      if (clientFilter && clientOf(row.project, roots) !== clientFilter) continue;
      if (section !== "all" && row.source !== section) continue;
      const date = row.date.slice(0, 10);
      byDate[date] = (byDate[date] ?? 0) + row.tokens;
    }
  }

  const dates = Object.keys(byDate).sort();
  const points: ChartPoint[] = [];
  if (dates.length === 0) return points;
  // Rellena los días sin actividad con 0 (cursor en UTC para no saltar/duplicar
  // días por el cambio de zona horaria).
  const cursor = new Date(`${dates[0]}T00:00:00Z`);
  const end = new Date(`${dates[dates.length - 1]}T00:00:00Z`);
  while (cursor <= end) {
    const date = cursor.toISOString().slice(0, 10);
    points.push({ date, label: formatDayShort(date), Tokens: byDate[date] ?? 0 });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return points;
}

export function TrendChart({ section, clientFilter, selectedDate, onSelectDate }: TrendChartProps) {
  const history = useHistory(HISTORY_DAYS);
  const roots = useClientRoots();
  // Día bajo el cursor (lo reporta el tooltip): permite seleccionar haciendo
  // clic en cualquier punto de la columna, no solo sobre el marcador de 5px.
  const hoveredDate = useRef<string | null>(null);

  const renderTooltip = ({ active, payload }: CustomTooltipProps) => {
    const point = active ? (payload?.[0]?.payload as ChartPoint | undefined) : undefined;
    hoveredDate.current = point?.date ?? null;
    if (!point) return null;
    return (
      <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-sm">
        <p className="font-medium">{formatDate(point.date)}</p>
        <p className="tabular-nums text-muted-foreground">{formatCompact(point.Tokens)} tokens</p>
      </div>
    );
  };

  const sourceMeta = section !== "all" ? SOURCE_META[section] : undefined;
  // El color sigue a la entidad: la línea de una fuente usa su color de identidad;
  // la vista agregada ("Todo") no es ninguna fuente, así que va en tinta neutra.
  const strokeStyle = { "--trend-stroke": sourceMeta?.color ?? "var(--foreground)" } as CSSProperties;

  const chartData = history.status === "ready" ? buildSeries(history.data, section, clientFilter, roots) : [];
  const nonZero = chartData.filter((d) => d.Tokens > 0);
  const avg = nonZero.length ? nonZero.reduce((s, d) => s + d.Tokens, 0) / nonZero.length : 0;
  const max = chartData.reduce((m, d) => Math.max(m, d.Tokens), 0);

  return (
    <section aria-labelledby="trend-title" className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id="trend-title" className="font-semibold">
          Tendencia de tokens ({HISTORY_DAYS} días)
          {sourceMeta ? ` — ${sourceMeta.label}` : ""}
        </h2>
        {history.status === "ready" && chartData.length > 0 && (
          <dl className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
            <div className="flex gap-1.5"><dt>Promedio/día activo</dt><dd className="text-foreground font-medium tabular-nums">{formatCompact(avg)}</dd></div>
            <div className="flex gap-1.5"><dt>Pico</dt><dd className="text-foreground font-medium tabular-nums">{formatCompact(max)}</dd></div>
            <div className="flex gap-1.5"><dt>Días activos</dt><dd className="text-foreground font-medium tabular-nums">{nonZero.length}/{chartData.length}</dd></div>
          </dl>
        )}
      </div>

      {history.status === "loading" && (
        <div aria-busy="true" aria-label="Cargando tendencia" className="mt-4 space-y-3">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {history.status === "error" && (
        <div role="alert" className="mt-4 flex h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed text-sm">
          <p className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
            No se pudo cargar el historial.
          </p>
          <p className="text-xs text-muted-foreground">{history.message}</p>
          <button
            type="button"
            onClick={history.retry}
            className="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <RotateCw className="h-4 w-4" aria-hidden />
            Reintentar
          </button>
        </div>
      )}

      {history.status === "ready" && chartData.length === 0 && (
        <div className="mt-4 flex h-64 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
          Sin actividad registrada en los últimos {HISTORY_DAYS} días
          {clientFilter ? ` para ${clientFilter}` : ""}.
        </div>
      )}

      {history.status === "ready" && chartData.length > 0 && (
        <>
          <div className="mt-3 flex min-h-7 flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {selectedDate ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-foreground">
                Día seleccionado: <span className="font-medium">{formatDate(selectedDate)}</span>
                <button
                  type="button"
                  onClick={() => onSelectDate?.(null)}
                  aria-label="Quitar filtro de día"
                  className="-mr-1 rounded-full p-0.5 hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ) : (
              onSelectDate && (
                <span className="inline-flex items-center gap-1.5">
                  <MousePointerClick className="h-3.5 w-3.5" aria-hidden />
                  Haz clic en un día para ver sus sesiones
                </span>
              )
            )}
          </div>
          <LineChart
            data={chartData}
            index="label"
            categories={["Tokens"]}
            colors={["blue"]}
            valueFormatter={formatCompact}
            yAxisWidth={56}
            showLegend={false}
            customTooltip={renderTooltip}
            className={`ai-monitor-trendchart mt-2 h-64 ${onSelectDate ? "cursor-pointer" : ""}`}
            style={strokeStyle}
            onClick={() => {
              const date = hoveredDate.current;
              if (!date || !onSelectDate) return;
              // Clic sobre el día ya seleccionado lo deselecciona.
              onSelectDate(date === selectedDate ? null : date);
            }}
          />
        </>
      )}
    </section>
  );
}

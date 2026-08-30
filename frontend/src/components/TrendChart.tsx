import { useEffect, useState } from "react";
import { LineChart } from "@tremor/react";

interface DailyProjectRow {
  date: string;
  source: string;
  project: string;
  tokens: number;
  cost: number;
}

interface TrendChartProps {
  onSelectDate?: (date: string) => void;
}

export function TrendChart({ onSelectDate }: TrendChartProps) {
  const [rows, setRows] = useState<DailyProjectRow[]>([]);

  useEffect(() => {
    fetch("/api/history?days=90")
      .then((r) => r.json())
      .then((data) => setRows(data.daily_project))
      .catch((err) => console.error("Error al cargar /api/history:", err));
  }, []);

  const byDate: Record<string, number> = {};
  for (const row of rows) {
    byDate[row.date] = (byDate[row.date] ?? 0) + row.tokens;
  }

  const dates = Object.keys(byDate).sort();
  const chartData: { date: string; Tokens: number }[] = [];
  if (dates.length > 0) {
    const cursor = new Date(dates[0]);
    const end = new Date(dates[dates.length - 1]);
    while (cursor <= end) {
      const date = cursor.toISOString().slice(0, 10);
      chartData.push({ date, Tokens: byDate[date] ?? 0 });
      cursor.setDate(cursor.getDate() + 1);
    }
  }

  const formatTokens = (value: number) =>
    new Intl.NumberFormat("es", { notation: "compact", maximumFractionDigits: 1 }).format(value);

  const nonZero = chartData.filter((d) => d.Tokens > 0);
  const avg = nonZero.length ? nonZero.reduce((s, d) => s + d.Tokens, 0) / nonZero.length : 0;
  const max = chartData.reduce((m, d) => Math.max(m, d.Tokens), 0);
  const activeDays = nonZero.length;

  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 mb-4">
        <h2 className="font-semibold">Tendencia de tokens (90 días)</h2>
        <div className="flex gap-5 text-sm text-muted-foreground">
          <span>Promedio/día activo <span className="text-foreground font-medium tabular-nums">{formatTokens(avg)}</span></span>
          <span>Pico <span className="text-foreground font-medium tabular-nums">{formatTokens(max)}</span></span>
          <span>Días activos <span className="text-foreground font-medium tabular-nums">{activeDays}/{chartData.length}</span></span>
        </div>
      </div>
      <LineChart
        data={chartData}
        index="date"
        categories={["Tokens"]}
        colors={["blue"]}
        valueFormatter={formatTokens}
        yAxisWidth={64}
        showLegend={false}
        className="ai-monitor-trendchart h-64 mt-4 cursor-pointer"
        onValueChange={(v) => {
          const date = v?.date;
          if (typeof date === "string" && onSelectDate) onSelectDate(date);
        }}
      />
    </div>
  );
}

import { useEffect, useState } from "react";
import { Card, Title, LineChart } from "@tremor/react";

interface DailyProjectRow {
  date: string;
  source: string;
  project: string;
  tokens: number;
  cost: number;
}

export function TrendChart() {
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

  return (
    <Card>
      <Title>Tendencia de tokens (90 días)</Title>
      <LineChart
        data={chartData}
        index="date"
        categories={["Tokens"]}
        colors={["blue"]}
        valueFormatter={formatTokens}
        yAxisWidth={64}
        showLegend={false}
        className="ai-monitor-trendchart h-64 mt-4"
      />
    </Card>
  );
}

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
      .then((data) => setRows(data.daily_project));
  }, []);

  const byDate: Record<string, number> = {};
  for (const row of rows) {
    byDate[row.date] = (byDate[row.date] ?? 0) + row.tokens;
  }
  const chartData = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, tokens]) => ({ date, Tokens: tokens }));

  return (
    <Card>
      <Title>Tendencia de tokens (90 días)</Title>
      <LineChart
        data={chartData}
        index="date"
        categories={["Tokens"]}
        colors={["blue"]}
        className="h-64 mt-4"
      />
    </Card>
  );
}

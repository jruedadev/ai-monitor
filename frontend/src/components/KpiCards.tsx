import { Card, Metric, Text } from "@tremor/react";
import type { ProjectUsage } from "@/lib/api";

interface KpiCardsProps {
  projects: Record<string, ProjectUsage>;
}

export function KpiCards({ projects }: KpiCardsProps) {
  const rows = Object.values(projects);
  const totalTokens = rows.reduce((s, r) => s + r.total_tokens, 0);
  const totalCost = rows.reduce((s, r) => s + r.cost, 0);
  const totalSessions = rows.reduce((s, r) => s + r.session_count, 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <Card>
        <Text>Proyectos</Text>
        <Metric>{rows.length}</Metric>
      </Card>
      <Card>
        <Text>Tokens totales</Text>
        <Metric>{totalTokens.toLocaleString()}</Metric>
      </Card>
      <Card>
        <Text>Costo estimado</Text>
        <Metric>${totalCost.toFixed(2)}</Metric>
      </Card>
      <Card>
        <Text>Sesiones</Text>
        <Metric>{totalSessions}</Metric>
      </Card>
    </div>
  );
}

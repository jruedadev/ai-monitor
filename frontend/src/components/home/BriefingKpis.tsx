import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { BriefingResponse } from "@/lib/api";
import { coverageLabel, formatDeltaPct, subscriptionHeadline, subscriptionLine } from "@/lib/briefing";
import { formatCompact, formatInt, formatUsd } from "@/lib/format";
import { withSource } from "@/lib/routes";

function Delta({ value, label }: { value: number | null; label: string }) {
  if (value === null) {
    return (
      <span title="sin datos para comparar" className="text-muted-foreground">
        <span aria-hidden>—</span>
        <span className="sr-only">{label}: sin datos para comparar</span>
      </span>
    );
  }
  return (
    <span className="font-medium tabular-nums">
      <span className="sr-only">{label}: </span>
      {formatDeltaPct(value)}
    </span>
  );
}

function Kpi({ label, value, children }: { label: string; value: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight tabular-nums">{value}</p>
      <div className="mt-2 space-y-1 text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

export function BriefingKpis({ briefing, search }: { briefing: BriefingResponse; search: string }) {
  const { kpis, subscription, compare } = briefing;
  const partial = compare.coverage === "partial" && compare.since ? coverageLabel(compare.since) : null;
  const line = subscriptionLine(subscription);

  return (
    <section aria-label="Indicadores del mes" className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Kpi label="Gasto equivalente API" value={formatUsd(kpis.cost.current)}>
        <p>
          <Delta value={kpis.cost.delta_pct} label="Variación del gasto" /> frente al mes comparado
        </p>
        {partial && <p className="text-xs">{partial}</p>}
        {kpis.cost_incomplete && <p className="text-xs">Incluye consumo sin costo calculado</p>}
      </Kpi>
      <Kpi label="Suscripción vs API" value={subscriptionHeadline(subscription)}>
        {line ? (
          <p>{line}</p>
        ) : (
          <Link to={withSource("/configuracion", search)} className="text-link underline-offset-4 hover:underline">
            Configura tu plan para comparar
          </Link>
        )}
      </Kpi>
      <Kpi label="Días activos" value={formatInt(kpis.active_days.current)}>
        <p>
          {formatCompact(kpis.tokens.current)} tokens · <Delta value={kpis.tokens.delta_pct} label="Variación de tokens" />
        </p>
        {kpis.active_days.previous !== null && <p className="text-xs">Antes: {formatInt(kpis.active_days.previous)} días</p>}
      </Kpi>
    </section>
  );
}

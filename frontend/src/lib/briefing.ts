/**
 * Formato de presentación del briefing (/api/briefing). El backend ya decide
 * qué señales mostrar y arma sus textos; aquí solo se da forma a números y etiquetas.
 */
import type { BriefingResponse, BriefingSubscription, HistoryResponse } from "@/lib/api";
import { formatDayShort, formatDecimal, formatUsd } from "@/lib/format";
import type { SourceKey } from "@/lib/sources";

export function formatDeltaPct(delta: number | null): string {
  if (delta === null) return "—";
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
  return `${sign}${formatDecimal(Math.abs(delta))} %`;
}

export function coverageLabel(since: string): string {
  return `cobertura parcial desde ${formatDayShort(since)}`;
}

function dayRange(from: string, to: string): string {
  return `${Number(from.slice(8, 10))}–${formatDayShort(to)}`;
}

export function windowLabel(b: BriefingResponse): string {
  const current = dayRange(b.window.from, b.window.to);
  if (b.compare.coverage === "none") return `${current} · sin mes con datos para comparar`;
  return `${current} · comparado con ${dayRange(b.compare.from, b.compare.to)}`;
}

export function subscriptionLine(s: BriefingSubscription): string | null {
  if (!s.configured || s.paid === null || s.api_equivalent === null || s.savings === null) return null;
  const base = `Pagas ${formatUsd(s.paid)} · equivale a ${formatUsd(s.api_equivalent)}`;
  if (s.winner === "subscription") return `${base} · ahorras ${formatUsd(s.savings)}`;
  if (s.winner === "api") return `${base} · la API saldría ${formatUsd(s.savings)} más barata`;
  return `${base} · empate`;
}

export function subscriptionHeadline(s: BriefingSubscription): string {
  if (!s.configured || s.savings === null) return "Sin plan configurado";
  if (s.winner === "subscription") return `Ahorras ${formatUsd(s.savings)}`;
  if (s.winner === "api") return `API más barata por ${formatUsd(s.savings)}`;
  return "Empate";
}

export function isEmptyBriefing(b: BriefingResponse): boolean {
  return b.eligible_months.length === 0 && b.kpis.active_days.current === 0;
}

const PROJECT_SOURCES = new Set(["claude_code", "codex", "opencode", "hermes"]);

/** Costo por día entre `from` y `to` (inclusive), con 0 en los días sin filas. */
export function dailyCostSeries(
  data: HistoryResponse, source: SourceKey, from: string, to: string,
): { date: string; cost: number }[] {
  const byDate: Record<string, number> = {};
  if (source === "openrouter") {
    for (const row of data.daily_model) {
      if (row.model === "__all__") byDate[row.date.slice(0, 10)] = (byDate[row.date.slice(0, 10)] ?? 0) + (row.cost ?? 0);
    }
  } else {
    for (const row of data.daily_project) {
      if (source === "all" ? !PROJECT_SOURCES.has(row.source) : row.source !== source) continue;
      const date = row.date.slice(0, 10);
      byDate[date] = (byDate[date] ?? 0) + (row.cost ?? 0);
    }
  }
  const points: { date: string; cost: number }[] = [];
  // Cursor en UTC para no saltar ni duplicar días por la zona horaria.
  const cursor = new Date(`${from}T00:00:00Z`);
  const end = new Date(`${to}T00:00:00Z`);
  while (cursor <= end) {
    const date = cursor.toISOString().slice(0, 10);
    points.push({ date, cost: byDate[date] ?? 0 });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return points;
}

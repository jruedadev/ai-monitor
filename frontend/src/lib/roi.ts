/**
 * Lógica de negocio del ROI, sin React: suscripción vs. pago por uso (API) y
 * valor generado por las horas de sesión. Todo lo que compara costos usa la
 * MISMA ventana temporal: con fecha de inicio de suscripción, desde esa fecha
 * (costo API por historial diario); sin ella, el periodo completo del snapshot.
 */
import type { CostWinner, DailyProjectRow, SessionDetailEntry } from "@/lib/api";
import { sessionDurationSeconds } from "@/lib/sessions";

/** Qué opción sale más barata para el mismo consumo (definido en api.ts para evitar un ciclo de import). */
export type { CostWinner } from "@/lib/api";

export interface CostComparison {
  winner: CostWinner;
  /** Cuánto ahorra la opción ganadora frente a la otra (siempre ≥ 0). */
  savings: number;
}

export function compareCosts(apiCost: number, subscriptionCost: number): CostComparison {
  const diff = apiCost - subscriptionCost;
  // Redondeo a centavos: diferencias de coma flotante no deben dar un "ganador".
  const cents = Math.round(diff * 100);
  if (cents === 0) return { winner: "tie", savings: 0 };
  return { winner: cents > 0 ? "subscription" : "api", savings: Math.abs(diff) };
}

export function monthKey(date: string): string {
  return date.slice(0, 7);
}

/** Claves YYYY-MM desde el mes de `start` hasta el mes de `now`, ambos inclusive. */
export function monthRange(start: string, now: Date = new Date()): string[] {
  const [startYear, startMonth] = monthKey(start).split("-").map(Number);
  const endYear = now.getFullYear();
  const endMonth = now.getMonth() + 1;

  const keys: string[] = [];
  let year = startYear;
  let month = startMonth;
  while (year < endYear || (year === endYear && month <= endMonth)) {
    keys.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return keys;
}

export interface RoiSession extends Pick<SessionDetailEntry, "first_ts" | "last_ts"> {
  project: string;
  date: string | null;
}

export interface SourceRoiInput {
  source: string;
  /** Costo acumulado por proyecto en el snapshot actual (se usa sin fecha de inicio). */
  projectCosts: Record<string, number>;
  sessions: RoiSession[];
  historyRows: DailyProjectRow[];
  /** Costo mensual de la suscripción. */
  subscriptionCost: number | null;
  subscriptionStart: string | null;
  hourlyRate: number | null;
  matchesScope: (projectPath: string) => boolean;
  now?: Date;
}

export interface MonthlyRoi {
  key: string;
  apiCost: number;
  comparison: CostComparison | null;
}

export interface SourceRoi {
  apiCost: number;
  /** Suscripción acumulada en la ventana (mensual × meses); sin inicio, un mes. */
  subscriptionTotal: number | null;
  months: number;
  comparison: CostComparison | null;
  hours: number;
  valueGenerated: number | null;
  /** valor generado / costo API; null si no hay tarifa o no hubo costo. */
  roi: number | null;
  monthly: MonthlyRoi[];
}

export function computeSourceRoi(input: SourceRoiInput): SourceRoi {
  const { source, subscriptionCost, subscriptionStart, hourlyRate, matchesScope } = input;

  const sessions = input.sessions.filter(
    (s) => matchesScope(s.project) && (!subscriptionStart || (s.date !== null && s.date >= subscriptionStart)),
  );
  const hours = sessions.reduce((sum, s) => sum + sessionDurationSeconds(s), 0) / 3600;
  const valueGenerated = hourlyRate !== null ? hours * hourlyRate : null;

  const monthly: MonthlyRoi[] = subscriptionStart
    ? monthRange(subscriptionStart, input.now).map((key) => {
        const apiCost = input.historyRows
          .filter((row) => row.source === source && row.date >= subscriptionStart && monthKey(row.date) === key && matchesScope(row.project))
          .reduce((sum, row) => sum + (row.cost ?? 0), 0);
        return { key, apiCost, comparison: subscriptionCost !== null ? compareCosts(apiCost, subscriptionCost) : null };
      })
    : [];

  const apiCost = subscriptionStart
    ? monthly.reduce((sum, m) => sum + m.apiCost, 0)
    : Object.entries(input.projectCosts)
        .filter(([path]) => matchesScope(path))
        .reduce((sum, [, cost]) => sum + cost, 0);

  const subscriptionTotal =
    subscriptionCost === null ? null : subscriptionStart ? subscriptionCost * monthly.length : subscriptionCost;

  return {
    apiCost,
    subscriptionTotal,
    months: monthly.length,
    comparison: subscriptionTotal !== null ? compareCosts(apiCost, subscriptionTotal) : null,
    hours,
    valueGenerated,
    roi: valueGenerated !== null && apiCost > 0 ? valueGenerated / apiCost : null,
    monthly,
  };
}

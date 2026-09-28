/**
 * Único punto de formateo numérico del dashboard. `es-CO` porque es el único
 * locale español que agrupa también los números de 4 cifras (el `es` genérico
 * deja `1234` sin separador) y usa `.` de miles / `,` decimal de forma consistente.
 */
const LOCALE = "es-CO";

const usd = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "USD", currencyDisplay: "narrowSymbol" });
const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat(LOCALE, { notation: "compact", maximumFractionDigits: 1 });
const oneDecimal = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const formatUsd = (value: number) => usd.format(value);
export const formatInt = (value: number) => integer.format(value);
export const formatCompact = (value: number) => compact.format(value);
export const formatDecimal = (value: number) => oneDecimal.format(value);

const monthYear = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric" });
const dayMonth = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short" });
const fullDate = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short", year: "numeric" });

/** "YYYY-MM-DD" como fecha local (new Date("YYYY-MM-DD") es UTC y en UTC-5 retrocede un día). */
function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day || 1);
}

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** "2026-04" → "Abril de 2026" (solo la primera letra en mayúscula, no "Abril De 2026"). */
export const formatMonth = (yearMonth: string) => capitalize(monthYear.format(parseIsoDate(yearMonth)));
/** "2026-07-18" → "18 jul" */
export const formatDayShort = (iso: string) => dayMonth.format(parseIsoDate(iso)).replace(/\./g, "").replace(/ de /g, " ");
/** "2026-07-18" → "18 jul 2026" */
export const formatDate = (iso: string) => fullDate.format(parseIsoDate(iso)).replace(/\./g, "").replace(/ de /g, " ");

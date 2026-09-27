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

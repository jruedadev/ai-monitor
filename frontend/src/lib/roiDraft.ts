import type { Account, RoiSettings } from "@/lib/api";
import type { SourceStatus } from "@/lib/settings";

/** Borrador de formulario: todo como texto; "" = sin valor. */
export type RoiDraft = Record<keyof RoiSettings, string>;
export type RoiPlan = "claude" | "codex";

export function toRoiDraft(s: RoiSettings): RoiDraft {
  return {
    subscription_cost_claude: s.subscription_cost_claude?.toString() ?? "",
    subscription_cost_codex: s.subscription_cost_codex?.toString() ?? "",
    hourly_rate: s.hourly_rate?.toString() ?? "",
    subscription_start_claude: s.subscription_start_claude ?? "",
    subscription_start_codex: s.subscription_start_codex ?? "",
  };
}

export function roiPayload(d: RoiDraft, omitClaude = false): Partial<RoiSettings> {
  const full = roiPayloadFull(d);
  if (!omitClaude) return full;
  const { subscription_cost_claude: _cost, subscription_start_claude: _start, ...rest } = full;
  return rest;
}

function roiPayloadFull(d: RoiDraft): Partial<RoiSettings> {
  return {
    subscription_cost_claude: d.subscription_cost_claude ? Number(d.subscription_cost_claude) : null,
    subscription_cost_codex: d.subscription_cost_codex ? Number(d.subscription_cost_codex) : null,
    hourly_rate: d.hourly_rate ? Number(d.hourly_rate) : null,
    subscription_start_claude: d.subscription_start_claude || null,
    subscription_start_codex: d.subscription_start_codex || null,
  };
}

/** Planes con suscripción que tiene sentido pedir: los de fuentes con datos. */
export function plansWithData(statuses: SourceStatus[]): RoiPlan[] {
  const withData = new Set(statuses.filter((s) => s.state === "data").map((s) => s.key));
  return (["claude", "codex"] as const).filter((plan) => withData.has(plan === "claude" ? "claude_code" : "codex"));
}

/** Borrador de una cuenta de suscripción; mismas reglas que accounts.py del backend. */
export type AccountDraft = Account;

const ID_RE = /^[a-z0-9-]{1,32}$/;
const RESERVED_IDS = ["all", "openrouter"];
const DEFAULT_PROVIDER = "claude_code";

/** Primer problema (en español) o null si la lista de cuentas es válida. */
export function validateAccountDrafts(drafts: AccountDraft[]): string | null {
  const seen = new Set<string>();
  for (const a of drafts) {
    const name = a.label.trim() || a.id || "sin nombre";
    if (!ID_RE.test(a.id)) return `La cuenta "${name}" tiene un id inválido: usa a-z, 0-9 y guion (máx. 32).`;
    if (RESERVED_IDS.includes(a.id)) return `El id "${a.id}" está reservado.`;
    if (seen.has(a.id)) return `Hay ids de cuenta repetidos: "${a.id}".`;
    seen.add(a.id);
    if (!a.label.trim() || a.label.length > 40) return `Cada cuenta necesita un nombre de hasta 40 caracteres (id "${a.id}").`;
    if (!a.location.startsWith("/")) return `El directorio de "${name}" debe ser una ruta absoluta (por ejemplo /home/tu-usuario/.claude).`;
    if (a.monthly_cost !== null && (!Number.isFinite(a.monthly_cost) || a.monthly_cost < 0)) {
      return `El costo mensual de "${name}" debe ser un número mayor o igual a 0.`;
    }
    if (a.start_date !== null && !/^\d{4}-\d{2}-\d{2}$/.test(a.start_date)) {
      return `La fecha de inicio de "${name}" debe tener el formato AAAA-MM-DD.`;
    }
  }
  const defaults = drafts.filter((a) => a.provider === DEFAULT_PROVIDER && a.default);
  if (defaults.length !== 1) return "Debe haber exactamente una cuenta de Claude Code por defecto.";
  return null;
}

export function addAccountDraft(drafts: AccountDraft[], provider: "claude_code"): AccountDraft[] {
  const ids = new Set(drafts.map((a) => a.id));
  let n = drafts.length + 1;
  while (ids.has(`cuenta-${n}`)) n += 1;
  return [...drafts, {
    id: `cuenta-${n}`, provider, label: `Cuenta ${n}`, location: "", default: false, monthly_cost: null, start_date: null,
  }];
}

/** La cuenta por defecto no se puede quitar: primero hay que marcar otra como default. */
export function removeAccountDraft(drafts: AccountDraft[], id: string): AccountDraft[] {
  const target = drafts.find((a) => a.id === id);
  if (!target) return drafts;
  if (target.default && drafts.filter((a) => a.provider === target.provider && a.default).length === 1) return drafts;
  return drafts.filter((a) => a.id !== id);
}

/** Marca una cuenta como la única default de su proveedor. */
export function setDefaultAccountDraft(drafts: AccountDraft[], id: string): AccountDraft[] {
  const target = drafts.find((a) => a.id === id);
  if (!target) return drafts;
  return drafts.map((a) => (a.provider === target.provider ? { ...a, default: a.id === id } : a));
}

export function updateAccountDraft(drafts: AccountDraft[], id: string, patch: Partial<AccountDraft>): AccountDraft[] {
  return drafts.map((a) => (a.id === id ? { ...a, ...patch } : a));
}

/** La cuenta por defecto guardada no puede cambiar (reinterpretaría el histórico): ni su marca ni su ubicación. */
export function hasSavedDefault(saved: AccountDraft[], provider: AccountDraft["provider"] = DEFAULT_PROVIDER): boolean {
  return saved.some((a) => a.provider === provider && a.default);
}

/** El directorio de la cuenta por defecto ya guardada es de solo lectura. */
export function isLocationLocked(saved: AccountDraft[], account: AccountDraft): boolean {
  return saved.some((a) => a.id === account.id && a.default);
}

/** Con cuentas guardadas, el plan de Claude se edita en "Cuentas de suscripción", no en los campos de ROI. */
export function roiPlansForAccounts(plans: RoiPlan[], accounts: AccountDraft[]): RoiPlan[] {
  return accounts.length > 0 ? plans.filter((plan) => plan !== "claude") : plans;
}

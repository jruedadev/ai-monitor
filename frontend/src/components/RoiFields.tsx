import { Trash2 } from "lucide-react";
import type { AccountDraft, RoiDraft, RoiPlan } from "@/lib/roiDraft";

interface RoiFieldsProps {
  draft: RoiDraft;
  onChange: (key: keyof RoiDraft, value: string) => void;
  /** Planes a mostrar; la tarifa por hora aparece siempre. */
  plans?: RoiPlan[];
}

export function RoiFields({ draft, onChange, plans = ["claude", "codex"] }: RoiFieldsProps) {
  const claude = plans.includes("claude");
  const codex = plans.includes("codex");
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {claude && <Field label="Suscripción Claude ($/mes)" value={draft.subscription_cost_claude} onChange={(v) => onChange("subscription_cost_claude", v)} />}
        {codex && <Field label="Suscripción Codex ($/mes)" value={draft.subscription_cost_codex} onChange={(v) => onChange("subscription_cost_codex", v)} />}
        <Field label="Tarifa por hora ($)" value={draft.hourly_rate} onChange={(v) => onChange("hourly_rate", v)} />
      </div>
      {(claude || codex) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {claude && <Field type="date" label="Inicio suscripción Claude" value={draft.subscription_start_claude} onChange={(v) => onChange("subscription_start_claude", v)} />}
          {codex && <Field type="date" label="Inicio suscripción Codex" value={draft.subscription_start_codex} onChange={(v) => onChange("subscription_start_codex", v)} />}
        </div>
      )}
    </>
  );
}

function Field({ label, value, onChange, type = "number" }: {
  label: string; value: string; onChange: (v: string) => void; type?: "number" | "date";
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type={type}
        {...(type === "number" ? { min: "0", step: "0.01", placeholder: "—" } : {})}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
      />
    </label>
  );
}

interface AccountFieldsProps {
  account: AccountDraft;
  onChange: (patch: Partial<AccountDraft>) => void;
  onSetDefault: () => void;
  onRemove: () => void;
  canRemove: boolean;
  /** La cuenta por defecto guardada no cambia: radio deshabilitado y ubicación de solo lectura. */
  defaultLocked?: boolean;
  locationLocked?: boolean;
}

/** Una fila por cuenta: nombre, directorio de configuración, costo, inicio, default y quitar. */
export function AccountFields({ account, onChange, onSetDefault, onRemove, canRemove, defaultLocked = false, locationLocked = false }: AccountFieldsProps) {
  return (
    <fieldset className="space-y-3 rounded-lg border p-4">
      <legend className="px-1 text-xs text-muted-foreground">Cuenta {account.id}</legend>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <TextField label="Nombre" value={account.label} onChange={(v) => onChange({ label: v })} maxLength={40} />
        <TextField label="Directorio de Claude (ruta absoluta)" value={account.location} placeholder="/ruta/absoluta/a/.claude" readOnly={locationLocked} onChange={(v) => onChange({ location: v })} />
        <Field label="Costo mensual ($)" value={account.monthly_cost?.toString() ?? ""} onChange={(v) => onChange({ monthly_cost: v === "" ? null : Number(v) })} />
        <Field type="date" label="Inicio de la suscripción" value={account.start_date ?? ""} onChange={(v) => onChange({ start_date: v || null })} />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="radio" name="default-claude-account" checked={account.default} disabled={defaultLocked} onChange={onSetDefault} />
          Cuenta por defecto
          {defaultLocked && <span className="text-xs text-muted-foreground">(no se puede cambiar: reinterpretaría el histórico)</span>}
        </label>
        <button
          type="button"
          onClick={onRemove}
          disabled={!canRemove}
          title={canRemove ? undefined : "La cuenta por defecto no se puede quitar: marca otra como por defecto primero."}
          className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" aria-hidden />Quitar
        </button>
      </div>
    </fieldset>
  );
}

function TextField({ label, value, onChange, placeholder, maxLength, readOnly }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; maxLength?: number; readOnly?: boolean;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
      />
    </label>
  );
}

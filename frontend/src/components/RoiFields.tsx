import type { RoiDraft, RoiPlan } from "@/lib/roiDraft";

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

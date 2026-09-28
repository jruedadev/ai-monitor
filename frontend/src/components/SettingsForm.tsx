import { useEffect, useState } from "react";
import { AlertCircle, Check, Save } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchRoiSettings, saveRoiSettings, type RoiSettings } from "@/lib/api";

type Draft = Record<keyof RoiSettings, string>;

function toDraft(s: RoiSettings): Draft {
  return {
    subscription_cost_claude: s.subscription_cost_claude?.toString() ?? "",
    subscription_cost_codex: s.subscription_cost_codex?.toString() ?? "",
    hourly_rate: s.hourly_rate?.toString() ?? "",
    subscription_start_claude: s.subscription_start_claude ?? "",
    subscription_start_codex: s.subscription_start_codex ?? "",
  };
}

export function SettingsForm() {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    fetchRoiSettings().then((s) => setDraft(toDraft(s))).catch((err: Error) => setLoadError(err.message));
  }, []);

  // Cualquier edición posterior invalida el "Cambios guardados" / error anterior.
  useEffect(() => setSaveStatus("idle"), [draft]);

  if (loadError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-xl border bg-card p-5 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        No se pudo cargar la configuración ({loadError}).
      </div>
    );
  }
  if (!draft) return <Skeleton className="h-72 w-full rounded-xl" />;

  const update = (key: keyof RoiSettings) => (value: string) => setDraft((d) => (d ? { ...d, [key]: value } : d));

  const handleSave = async () => {
    setSaveStatus("saving");
    const payload: Partial<RoiSettings> = {
      subscription_cost_claude: draft.subscription_cost_claude ? Number(draft.subscription_cost_claude) : null,
      subscription_cost_codex: draft.subscription_cost_codex ? Number(draft.subscription_cost_codex) : null,
      hourly_rate: draft.hourly_rate ? Number(draft.hourly_rate) : null,
      subscription_start_claude: draft.subscription_start_claude || null,
      subscription_start_codex: draft.subscription_start_codex || null,
    };
    try {
      setDraft(toDraft(await saveRoiSettings(payload)));
      setSaveStatus("saved");
    } catch (err) {
      console.error("Error al guardar /api/roi-settings:", err);
      setSaveStatus("error");
    }
  };

  return (
    <section aria-labelledby="plan-title" className="space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 id="plan-title" className="text-sm font-medium">Tu plan</h2>
        <p className="text-sm text-muted-foreground">
          Con el costo mensual el Inicio y ROI comparan tu suscripción contra el precio de la API; la tarifa por hora estima el valor generado.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Suscripción Claude ($/mes)" value={draft.subscription_cost_claude} onChange={update("subscription_cost_claude")} />
        <Field label="Suscripción Codex ($/mes)" value={draft.subscription_cost_codex} onChange={update("subscription_cost_codex")} />
        <Field label="Tarifa por hora ($)" value={draft.hourly_rate} onChange={update("hourly_rate")} />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field type="date" label="Inicio suscripción Claude" value={draft.subscription_start_claude} onChange={update("subscription_start_claude")} />
        <Field type="date" label="Inicio suscripción Codex" value={draft.subscription_start_codex} onChange={update("subscription_start_codex")} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saveStatus === "saving"}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <Save className="h-4 w-4" aria-hidden />
          {saveStatus === "saving" ? "Guardando…" : "Guardar"}
        </button>
        <span role="status" aria-live="polite" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          {saveStatus === "saved" && (<><Check className="h-4 w-4" aria-hidden />Cambios guardados</>)}
          {saveStatus === "error" && (
            <><AlertCircle className="h-4 w-4 text-destructive" aria-hidden />No se pudo guardar. Revisa que el servidor siga activo e inténtalo de nuevo.</>
          )}
        </span>
      </div>
    </section>
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

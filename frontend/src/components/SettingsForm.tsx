import { useEffect, useState } from "react";
import { AlertCircle, Check, Save } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { RoiFields } from "@/components/RoiFields";
import { fetchRoiSettings, saveRoiSettings } from "@/lib/api";
import { roiPayload, toRoiDraft, type RoiDraft } from "@/lib/roiDraft";

export function SettingsForm() {
  const [draft, setDraft] = useState<RoiDraft | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    fetchRoiSettings().then((s) => setDraft(toRoiDraft(s))).catch((err: Error) => setLoadError(err.message));
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

  const update = (key: keyof RoiDraft, value: string) => setDraft((d) => (d ? { ...d, [key]: value } : d));

  const handleSave = async () => {
    setSaveStatus("saving");
    try {
      setDraft(toRoiDraft(await saveRoiSettings(roiPayload(draft))));
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
      <RoiFields draft={draft} onChange={update} />
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

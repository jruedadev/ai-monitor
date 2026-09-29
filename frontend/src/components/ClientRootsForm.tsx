import { useState } from "react";
import { AlertCircle, Check, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ClientRootsEditor } from "@/components/ClientRootsEditor";
import { useAppSettings } from "@/hooks/appSettingsContext";
import { errorDetail, saveAppSettings } from "@/lib/api";
import type { ClientRoot } from "@/lib/clients";

export function ClientRootsForm({ paths }: { paths: string[] }) {
  const { roots, reload } = useAppSettings();
  const [draft, setDraft] = useState<ClientRoot[] | null>(null);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const current = draft ?? roots;

  const handleSave = async () => {
    setStatus("saving");
    setError(null);
    try {
      await saveAppSettings({ client_roots: current });
      await reload();
      setDraft(null);
      setStatus("saved");
    } catch (err) {
      setError(errorDetail(err));
      setStatus("error");
    }
  };

  return (
    <section aria-labelledby="roots-title" className="space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 id="roots-title" className="text-sm font-medium">Carpetas de clientes</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Cómo se agrupan tus proyectos por cliente. Usa un nombre de carpeta (en cualquier nivel) o una ruta absoluta; gana la primera que coincide.
        </p>
      </div>
      <ClientRootsEditor roots={current} onChange={(next) => { setDraft(next); setStatus("idle"); }} paths={paths} />
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={handleSave} disabled={status === "saving"}><Save aria-hidden />Guardar</Button>
        <span role="status" className="text-sm">
          {status === "saved" && <span className="inline-flex items-center gap-1"><Check className="h-4 w-4" aria-hidden />Cambios guardados</span>}
          {status === "error" && (
            <span className="inline-flex items-center gap-1 text-destructive">
              <AlertCircle className="h-4 w-4" aria-hidden />No se pudo guardar{error ? `: ${error}` : ". Revisa que el servidor siga activo."}
            </span>
          )}
        </span>
      </div>
    </section>
  );
}

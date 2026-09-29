import { useEffect, useState } from "react";
import { AlertCircle, Check, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { HttpError, fetchEngineSettings, saveEngineSettings, type EngineBackend } from "@/lib/api";
import { BACKEND_OPTIONS, parseChain } from "@/lib/recommendations";

interface Draft {
  backend: EngineBackend;
  chain: string;
}

export function EngineSettingsForm() {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    fetchEngineSettings()
      .then((s) => setDraft({ backend: s.backend, chain: s.llm_chain.join("\n") }))
      .catch((err: Error) => setLoadError(err.message));
  }, []);

  if (loadError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-xl border bg-card p-5 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        No se pudo cargar la configuración del motor ({loadError}).
      </div>
    );
  }
  if (!draft) return <Skeleton className="h-64 w-full rounded-xl" />;

  const edit = (next: Partial<Draft>) => {
    setDraft({ ...draft, ...next });
    setSaveStatus("idle");
  };

  const handleSave = async () => {
    setSaveStatus("saving");
    setSaveError(null);
    try {
      const saved = await saveEngineSettings({ backend: draft.backend, llm_chain: parseChain(draft.chain) });
      setDraft({ backend: saved.backend, chain: saved.llm_chain.join("\n") });
      setSaveStatus("saved");
    } catch (err) {
      setSaveError(err instanceof HttpError && err.status === 400 ? err.message.split(": ").slice(1).join(": ") : null);
      setSaveStatus("error");
    }
  };

  return (
    <section aria-labelledby="engine-title" className="space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 id="engine-title" className="text-sm font-medium">Motor de recomendaciones</h2>
        <p className="mt-1 text-xs text-muted-foreground">Qué modelo redacta las recomendaciones de la corrida diaria y de Analizar ahora.</p>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm">Backend</legend>
        {BACKEND_OPTIONS.map((option) => (
          <label key={option.value} className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="engine-backend"
              value={option.value}
              checked={draft.backend === option.value}
              onChange={() => edit({ backend: option.value })}
              className="mt-1"
            />
            <span className="min-w-0">
              <span className="font-medium">{option.label}</span>
              <span className="block text-xs text-muted-foreground">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="block space-y-1 text-sm">
        <span>Cadena de modelos (uno por línea, en orden de preferencia; formato proveedor:modelo)</span>
        <textarea
          value={draft.chain}
          onChange={(e) => edit({ chain: e.target.value })}
          disabled={draft.backend !== "hermes"}
          rows={4}
          spellCheck={false}
          className="w-full rounded-lg border bg-background p-2 font-mono text-xs disabled:opacity-60"
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={handleSave} disabled={saveStatus === "saving"}>
          <Save aria-hidden />Guardar
        </Button>
        <span role="status" className="text-sm">
          {saveStatus === "saved" && <span className="inline-flex items-center gap-1"><Check className="h-4 w-4" aria-hidden />Cambios guardados</span>}
          {saveStatus === "error" && <span className="text-destructive">No se pudo guardar{saveError ? `: ${saveError}` : ""}</span>}
        </span>
      </div>
    </section>
  );
}
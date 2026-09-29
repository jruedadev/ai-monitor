import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ClientRootsEditor } from "@/components/ClientRootsEditor";
import { RoiFields } from "@/components/RoiFields";
import { useAppSettings } from "@/hooks/appSettingsContext";
import {
  completeOnboarding, fetchEngineSettings, fetchRoiSettings, saveAppSettings, saveEngineSettings, saveRoiSettings,
  type AvailableBackends, type EngineBackend, type UsageSnapshot,
} from "@/lib/api";
import type { ClientRoot } from "@/lib/clients";
import { ONBOARDING_STEPS, saveOnboarding, skipOutcome, suggestBackend, suggestRoots, type OnboardingDraft } from "@/lib/onboarding";
import { BACKEND_OPTIONS, parseChain } from "@/lib/recommendations";
import { plansWithData, roiPayload, toRoiDraft, type RoiDraft } from "@/lib/roiDraft";
import { projectPaths, sourceStatuses } from "@/lib/settings";

const API = { saveAppSettings, saveRoiSettings, saveEngineSettings, completeOnboarding };
const TITLES = { folders: "Carpetas de clientes", roi: "Tu plan", engine: "Motor de recomendaciones" } as const;

interface Loaded {
  roi: RoiDraft;
  backend: EngineBackend;
  chain: string;
  available: AvailableBackends;
}

export function OnboardingView({ sources }: { sources: UsageSnapshot["sources"] | null }) {
  const navigate = useNavigate();
  const { roots: savedRoots, completedAt, reload } = useAppSettings();
  const firstTime = completedAt === null;
  const paths = projectPaths(sources);
  const statuses = sourceStatuses(sources);

  const [step, setStep] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [roots, setRoots] = useState<ClientRoot[] | null>(firstTime ? null : savedRoots);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchRoiSettings(), fetchEngineSettings()])
      .then(([roi, engine]) => setLoaded({
        roi: toRoiDraft(roi),
        backend: firstTime ? suggestBackend(engine.available) : engine.backend,
        chain: engine.llm_chain.join("\n"),
        available: engine.available,
      }))
      .catch((err: Error) => setLoadError(err.message));
  }, [firstTime]);

  // Primera vez: la sugerencia se calcula cuando llega el snapshot con proyectos.
  // `roots === null` indica que el usuario aún no ha tocado las raíces.
  const effectiveRoots = roots ?? (sources ? suggestRoots(paths) : null);

  const finish = async (draft: OnboardingDraft) => {
    setSaving(true);
    setSaveError(null);
    const result = await saveOnboarding(draft, API);
    setSaving(false);
    if (!result.ok) {
      setStep(ONBOARDING_STEPS.indexOf(result.step));
      setSaveError(result.message);
      return;
    }
    await reload();
    navigate("/", { replace: true });
  };

  if (loadError) {
    return (
      <Shell>
        <div role="alert" className="flex items-center gap-2 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
          No se pudo cargar la configuración ({loadError}). Revisa que el servidor siga activo.
        </div>
      </Shell>
    );
  }
  if (!loaded || !effectiveRoots) return <Shell><Skeleton className="h-72 w-full rounded-xl" /></Shell>;

  const current = ONBOARDING_STEPS[step];
  const plans = plansWithData(statuses);
  const draft: OnboardingDraft = {
    roots: effectiveRoots,
    roi: roiPayload(loaded.roi),
    engine: { backend: loaded.backend, llm_chain: parseChain(loaded.chain) },
  };

  return (
    <Shell>
      <header className="space-y-1">
        <p className="text-xs text-muted-foreground">Paso {step + 1} de {ONBOARDING_STEPS.length}</p>
        <h1 className="text-xl font-semibold">{TITLES[current]}</h1>
      </header>

      {current === "folders" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Indica en qué carpeta guardas los proyectos de cada cliente. Con «La carpeta siguiente es el cliente», en <code>~/DEV/ACME/app</code> el cliente es ACME.
          </p>
          <SourcesSummary statuses={statuses} />
          <ClientRootsEditor roots={effectiveRoots} onChange={setRoots} paths={paths} />
        </div>
      )}

      {current === "roi" && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {plans.length > 0
              ? "Con el costo de tu suscripción el dashboard la compara contra el precio de la API. Puedes dejarlo vacío y completarlo después."
              : "Aún no hay datos de Claude Code ni de Codex; podrás indicar tu suscripción en Configuración cuando los haya."}
          </p>
          <RoiFields draft={loaded.roi} plans={plans} onChange={(key, value) => setLoaded({ ...loaded, roi: { ...loaded.roi, [key]: value } })} />
        </div>
      )}

      {current === "engine" && (
        <fieldset className="space-y-2">
          <legend className="text-sm text-muted-foreground">Qué modelo redacta las recomendaciones. Puedes cambiarlo en Configuración.</legend>
          {BACKEND_OPTIONS.map((option) => {
            const installed = option.value === "none" || loaded.available[option.value];
            return (
              <label key={option.value} className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="onboarding-backend"
                  value={option.value}
                  checked={loaded.backend === option.value}
                  disabled={!installed}
                  onChange={() => setLoaded({ ...loaded, backend: option.value })}
                  className="mt-1"
                />
                <span className={installed ? "" : "opacity-60"}>
                  <span className="font-medium">{option.label}</span>
                  <span className="block text-xs text-muted-foreground">
                    {installed ? option.hint : `No se encontró «${option.value}» en el PATH del servidor. Instálalo y vuelve a esta pantalla desde Configuración.`}
                  </span>
                </span>
              </label>
            );
          })}
        </fieldset>
      )}

      {saveError && (
        <p role="alert" className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden />{saveError}
        </p>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
        <Button variant="ghost" disabled={saving} onClick={() => {
          const skip = skipOutcome(completedAt, loaded.available, parseChain(loaded.chain));
          if (skip) finish(skip);
          else navigate("/configuracion");
        }}>
          {firstTime ? "Omitir" : "Cancelar"}
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" disabled={saving || step === 0} onClick={() => setStep(step - 1)}>Atrás</Button>
          {step < ONBOARDING_STEPS.length - 1 ? (
            <Button disabled={saving} onClick={() => { setSaveError(null); setStep(step + 1); }}>Siguiente</Button>
          ) : (
            <Button disabled={saving} onClick={() => finish(draft)}>{saving ? "Guardando…" : "Finalizar"}</Button>
          )}
        </div>
      </footer>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-svh items-start justify-center bg-background p-4 text-foreground md:items-center md:p-8">
      <div className="w-full max-w-2xl space-y-6 rounded-xl border bg-card p-5 md:p-8">
        <p className="font-mono text-xs text-muted-foreground">ai-monitor · configuración inicial</p>
        {children}
      </div>
    </main>
  );
}

function SourcesSummary({ statuses }: { statuses: ReturnType<typeof sourceStatuses> }) {
  if (statuses.length === 0) return <Skeleton className="h-6 w-full" />;
  return (
    <ul className="flex flex-wrap gap-1.5 text-xs">
      {statuses.map((s) => (
        <li key={s.key} className="rounded-full border px-2 py-0.5">
          {s.label}: {s.state === "data" ? s.detail : "sin datos"}
        </li>
      ))}
    </ul>
  );
}

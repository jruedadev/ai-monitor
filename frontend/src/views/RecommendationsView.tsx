// frontend/src/views/RecommendationsView.tsx
import { useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { AlertCircle, Loader2, RotateCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RecommendationCard } from "@/components/recommendations/RecommendationCard";
import { SectionFallback } from "@/views/SectionFallback";
import { useRecommendations } from "@/hooks/useRecommendations";
import { runRecommendations, setRecommendationStatus, type Recommendation, type UserStatus } from "@/lib/api";
import {
  REC_TABS, emptyMessage, filterBySource, isRunInProgress, parseRecTab, removeRecommendation,
  restoreRecommendation, runErrorMessage, runModelLabel,
} from "@/lib/recommendations";
import { REC_STATUS_PARAM, withQuery, withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";
import { cn } from "@/lib/utils";

const whenFormat = new Intl.DateTimeFormat("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

interface Props {
  source: SourceKey;
  refreshKey: unknown;
  onChange: () => void;
}

export function RecommendationsView({ source, refreshKey, onChange }: Props) {
  const { search } = useLocation();
  const [params] = useSearchParams();
  const tab = parseRecTab(params.get(REC_STATUS_PARAM));
  const { state, update, retry } = useRecommendations(tab, refreshKey);
  const [pendingRunId, setPendingRunId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const data = state.status === "ready" ? state.data : null;
  const running = isRunInProgress(data, pendingRunId);

  const analyze = async () => {
    setNotice(null);
    try {
      const { run_id } = await runRecommendations();
      setPendingRunId(run_id);
    } catch (err) {
      setNotice(runErrorMessage(err));
    }
  };

  const changeStatus = async (rec: Recommendation, status: UserStatus) => {
    setNotice(null);
    let removed: ReturnType<typeof removeRecommendation>["removed"] = null;
    update((d) => {
      const result = removeRecommendation(d.recommendations, rec.id);
      removed = result.removed;
      return { ...d, recommendations: result.next };
    });
    try {
      await setRecommendationStatus(rec.id, status);
      onChange();
    } catch (err) {
      update((d) => ({ ...d, recommendations: restoreRecommendation(d.recommendations, removed) }));
      setNotice(`No se pudo actualizar la recomendación (${err instanceof Error ? err.message : String(err)})`);
    }
  };

  const tabHref = (status: string) => {
    const next = new URLSearchParams(search);
    if (status === "nueva") next.delete(REC_STATUS_PARAM);
    else next.set(REC_STATUS_PARAM, status);
    return withQuery("/recomendaciones", next);
  };

  const last = data?.last_run ?? null;

  return (
    <div className="min-w-0 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="text-xl font-semibold">Recomendaciones</h1>
          {last && (
            <p className="break-words text-sm text-muted-foreground">
              Última corrida: {whenFormat.format(new Date(last.started_at))} · {runModelLabel(last)}
              {last.status === "degraded" && <span className="ml-2 rounded-full border px-2 py-0.5 text-xs">degradado (reglas)</span>}
              {last.status === "error" && <span className="ml-2 rounded-full border border-destructive/50 px-2 py-0.5 text-xs text-destructive">falló</span>}
            </p>
          )}
        </div>
        <Button onClick={analyze} disabled={running} aria-busy={running}>
          {running ? <Loader2 className="animate-spin" aria-hidden /> : <Sparkles aria-hidden />}
          {running ? "Analizando…" : "Analizar ahora"}
        </Button>
      </div>

      {notice && (
        <p role="status" className="flex items-center gap-2 rounded-lg border bg-muted px-3 py-2 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden />{notice}
        </p>
      )}
      {data?.degraded && (
        <p role="status" className="rounded-lg border bg-muted px-3 py-2 text-sm text-muted-foreground">
          Historial no disponible temporalmente
        </p>
      )}

      <nav aria-label="Estado de las recomendaciones" className="flex max-w-full flex-wrap gap-1 rounded-lg border p-1">
        {REC_TABS.map((t) => (
          <Link
            key={t.status}
            to={tabHref(t.status)}
            aria-current={tab === t.status ? "page" : undefined}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm",
              tab === t.status ? "bg-muted font-medium shadow-[inset_0_-2px_0_var(--primary)]" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        ))}
      </nav>

      {state.status === "loading" && <SectionFallback label="Cargando recomendaciones" />}
      {state.status === "error" && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-5 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
          <span className="min-w-0 flex-1 break-words">No se pudieron cargar las recomendaciones ({state.message}).</span>
          <Button variant="outline" size="sm" onClick={retry}><RotateCw aria-hidden />Reintentar</Button>
        </div>
      )}
      {data && (() => {
        const visible = filterBySource(data.recommendations, source);
        if (visible.length === 0) {
          return <p className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">{emptyMessage(tab, last)}</p>;
        }
        return (
          <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
            {visible.map((rec) => (
              <RecommendationCard key={rec.id} rec={rec} onStatus={(status) => changeStatus(rec, status)} />
            ))}
          </div>
        );
      })()}
      <p className="text-xs text-muted-foreground">
        Las recomendaciones se generan cada día a las 07:00. Configura el motor en{" "}
        <Link to={withSource("/configuracion", search)} className="text-link underline-offset-4 hover:underline">Configuración</Link>.
      </p>
    </div>
  );
}
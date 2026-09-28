import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { AlertCircle, RotateCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useBriefing } from "@/hooks/useBriefing";
import { isEmptyBriefing } from "@/lib/briefing";
import { withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";
import { AttentionList } from "./AttentionList";
import { BriefingHeader } from "./BriefingHeader";
import { BriefingKpis } from "./BriefingKpis";
import { DailySpark } from "./DailySpark";
import { TopProjects } from "./TopProjects";

interface HomeViewProps {
  source: SourceKey;
  compare: string | null;
  onCompareChange: (month: string | null) => void;
  refreshKey: unknown;
  newRecommendations: number;
}

/** Mismas alturas que el contenido final para que no salte el layout. */
function HomeSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando briefing" className="space-y-6">
      <div className="space-y-2"><Skeleton className="h-8 w-56" /><Skeleton className="h-4 w-72" /></div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-36 w-full rounded-xl" />)}
      </div>
      <Skeleton className="h-44 w-full rounded-xl" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-60 w-full rounded-xl" /><Skeleton className="h-60 w-full rounded-xl" />
      </div>
    </div>
  );
}

export function HomeView({ source, compare, onCompareChange, refreshKey, newRecommendations }: HomeViewProps) {
  const briefing = useBriefing(source, compare, refreshKey);
  const { search } = useLocation();

  // Un ?comparar= que ya no es elegible (enlace viejo u otra fuente) vuelve al mes por defecto.
  const invalidCompare = briefing.status === "error" && briefing.httpStatus === 400 && compare !== null;
  useEffect(() => {
    if (invalidCompare) onCompareChange(null);
  }, [invalidCompare, onCompareChange]);

  if (briefing.status === "loading" || invalidCompare) return <HomeSkeleton />;

  if (briefing.status === "error") {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-5 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        <span className="min-w-0 flex-1 break-words">No se pudo cargar el briefing ({briefing.message}).</span>
        <button
          type="button"
          onClick={briefing.retry}
          className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-medium hover:bg-muted"
        >
          <RotateCw className="h-4 w-4" aria-hidden />
          Reintentar
        </button>
      </div>
    );
  }

  const b = briefing.data;
  const degraded = b.degraded && (
    <p role="status" className="rounded-lg border bg-muted px-3 py-2 text-sm text-muted-foreground">
      Historial no disponible temporalmente
    </p>
  );

  if (isEmptyBriefing(b)) {
    return (
      <div className="space-y-4">
        {degraded}
        <div className="space-y-3 rounded-xl border bg-card p-8 text-center">
          <h1 className="text-lg font-semibold">Aún no hay historial</h1>
          <p className="mx-auto max-w-prose text-sm text-muted-foreground">
            ai-monitor registra un resumen diario cada vez que recolecta; vuelve después de tu primera sesión.
          </p>
          <Link to={withSource("/configuracion", search)} className="text-sm text-link underline-offset-4 hover:underline">
            Ir a Configuración
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {degraded}
      <BriefingHeader briefing={b} onCompareChange={onCompareChange} />
      <BriefingKpis briefing={b} search={search} />
      <AttentionList signals={b.attention} search={search} newRecommendations={newRecommendations} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TopProjects projects={b.top_projects} search={search} />
        <DailySpark source={source} from={b.window.from} to={b.window.to} search={search} />
      </div>
    </div>
  );
}

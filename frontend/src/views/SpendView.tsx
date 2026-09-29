import { Suspense, lazy } from "react";
import { useClientRoots } from "@/hooks/appSettingsContext";
import { Link, useLocation } from "react-router-dom";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { SectionFallback } from "@/views/SectionFallback";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { projectsFor } from "@/lib/projects";
import { withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";
import { cn } from "@/lib/utils";

const TrendChart = lazy(() => import("@/components/TrendChart").then((m) => ({ default: m.TrendChart })));
const RoiView = lazy(() => import("@/components/RoiView").then((m) => ({ default: m.RoiView })));

const TABS = [
  { key: "spend", path: "/gasto", label: "Gasto" },
  { key: "roi", path: "/gasto/roi", label: "ROI" },
] as const;

interface SpendViewProps {
  tab: "spend" | "roi";
  source: SourceKey;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onSelectProject: (project: string | null) => void;
}

export function SpendView({ tab, source, sources, combined, selectedDate, onSelectDate, onSelectProject }: SpendViewProps) {
  const { search } = useLocation();
  const roots = useClientRoots();
  const projects = projectsFor(sources, combined, source, null, roots);
  const openRouterUnavailable = source === "openrouter" && sources?.openrouter?.unavailable;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{tab === "roi" ? "ROI" : "Gasto"}</h1>
        <nav aria-label="Gasto y ROI" className="inline-flex rounded-lg border p-1">
          {TABS.map((t) => (
            <Link
              key={t.key}
              to={withSource(t.path, search)}
              aria-current={tab === t.key ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm",
                tab === t.key ? "bg-muted font-medium shadow-[inset_0_-2px_0_var(--primary)]" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </Link>
          ))}
        </nav>
      </div>
      {tab === "roi" ? (
        <Suspense fallback={<SectionFallback label="Cargando ROI" />}>
          <RoiView sources={sources} />
        </Suspense>
      ) : (
        <>
          <Suspense fallback={<SectionFallback label="Cargando tendencia" />}>
            <TrendChart section={source} selectedDate={selectedDate} onSelectDate={onSelectDate} />
          </Suspense>
          {openRouterUnavailable ? (
            <div className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
              OpenRouter no disponible{sources?.openrouter?.reason ? `: ${sources.openrouter.reason}` : "."}
            </div>
          ) : (
            combined && (
              <>
                <KpiCards projects={projects} />
                <ProjectTable projects={projects} onSelectProject={source === "openrouter" ? undefined : onSelectProject} />
              </>
            )
          )}
        </>
      )}
    </div>
  );
}

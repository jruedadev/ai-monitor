import { Suspense, lazy } from "react";
import { Navigate } from "react-router-dom";
import { useUsageStream } from "@/hooks/useUsageStream";
import { useDashboardRoute } from "@/hooks/useDashboardRoute";
import { AppSidebar } from "@/components/Sidebar";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { SessionDetail } from "@/components/SessionDetail";
import { ProjectDetailSheet } from "@/components/ProjectDetailSheet";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Skeleton } from "@/components/ui/skeleton";
import type { ProjectUsage } from "@/lib/api";
import { clientOf, groupProjectsByClient } from "@/lib/clients";

// Tremor/recharts pesan la mayor parte del bundle: se cargan aparte para que
// la tabla y los KPI pinten sin esperarlos.
const TrendChart = lazy(() => import("@/components/TrendChart").then((m) => ({ default: m.TrendChart })));
const RoiView = lazy(() => import("@/components/RoiView").then((m) => ({ default: m.RoiView })));

function SectionFallback({ label }: { label: string }) {
  return (
    <div aria-busy="true" aria-label={label} className="rounded-xl border bg-card p-5 space-y-3">
      <Skeleton className="h-5 w-56" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export default function App() {
  const {
    valid, section, client: clientFilter, selectedDate, selectedProject, setSelectedDate, setSelectedProject,
  } = useDashboardRoute();
  const { sources, combined, connected } = useUsageStream();

  const projectsByClient = groupProjectsByClient(Object.keys(combined ?? {}));

  const projectsForSection = (): Record<string, ProjectUsage> => {
    if (!sources || !combined) return {};

    let result: Record<string, ProjectUsage>;
    if (section === "all" || section === "roi") {
      result = combined;
    } else if (section === "openrouter") {
      const or = sources.openrouter;
      if (!or || or.unavailable || !or.models) return {};
      result = Object.fromEntries(
        Object.entries(or.models).map(([model, v]) => [
          model,
          { total_tokens: v.tokens, cost: v.cost, messages: v.requests, session_count: v.requests, by_source: ["openrouter"] },
        ]),
      );
    } else {
      result = Object.fromEntries(
        Object.entries(sources[section]).map(([name, v]) => [
          name,
          { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [section] },
        ]),
      );
    }

    if (clientFilter && section !== "roi") {
      result = Object.fromEntries(
        Object.entries(result).filter(([path]) => clientOf(path) === clientFilter),
      );
    }

    return result;
  };

  const openRouterUnavailable = section === "openrouter" && sources?.openrouter?.unavailable;

  const activeLabel = clientFilter
    ? `Proyectos — ${clientFilter}`
    : section === "all"
      ? "Vista general"
      : { claude_code: "Claude Code", codex: "Codex", opencode: "OpenCode", hermes: "Hermes", openrouter: "OpenRouter", roi: "ROI" }[section];

  if (!valid) return <Navigate to="/" replace />;

  return (
    <SidebarProvider className="bg-background text-foreground">
      <AppSidebar active={section} activeClient={clientFilter} projectsByClient={projectsByClient} />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <SidebarTrigger className="-ml-1" />
            <h1 className="truncate text-lg font-semibold">{activeLabel}</h1>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span
              role="status"
              aria-live="polite"
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                connected ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground"
              }`}
            >
              <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"}`} />
              {connected ? "En vivo" : "Conectando…"}
            </span>
            <ThemeToggle />
          </div>
        </header>
        {/* SidebarInset ya es el <main>; aquí un div para no anidar landmarks. */}
        <div key={section} className="flex-1 space-y-6 p-4 md:p-6 max-w-[1400px] w-full min-w-0">
          {section === "roi" ? (
            <div className="dashboard-section" style={{ animationDelay: "0ms" }}>
              <Suspense fallback={<SectionFallback label="Cargando ROI" />}>
                <RoiView sources={sources} />
              </Suspense>
            </div>
          ) : (
          <>
          <div className="dashboard-section" style={{ animationDelay: "0ms" }}>
            <Suspense fallback={<SectionFallback label="Cargando tendencia" />}>
              <TrendChart section={section} clientFilter={clientFilter} selectedDate={selectedDate} onSelectDate={setSelectedDate} />
            </Suspense>
          </div>
          {openRouterUnavailable ? (
            <div className="dashboard-section rounded-xl border bg-card p-6 text-sm text-muted-foreground" style={{ animationDelay: "60ms" }}>
              OpenRouter no disponible
              {sources?.openrouter?.reason ? `: ${sources.openrouter.reason}` : "."}
            </div>
          ) : (
            combined && (
              <>
                <div className="dashboard-section" style={{ animationDelay: "60ms" }}>
                  <KpiCards projects={projectsForSection()} />
                </div>
                <div className="dashboard-section" style={{ animationDelay: "120ms" }}>
                  <ProjectTable
                    projects={projectsForSection()}
                    onSelectProject={section === "openrouter" ? undefined : setSelectedProject}
                  />
                </div>
                <div className="dashboard-section" style={{ animationDelay: "180ms" }}>
                  <SessionDetail
                    sources={sources}
                    section={section}
                    clientFilter={clientFilter}
                    selectedDate={selectedDate}
                    onSelectDate={setSelectedDate}
                    onSelectProject={setSelectedProject}
                  />
                </div>
              </>
            )
          )}
          </>
          )}
        </div>
      </SidebarInset>
      <ProjectDetailSheet
        sources={sources}
        section={section}
        project={selectedProject}
        onClose={() => setSelectedProject(null)}
      />
    </SidebarProvider>
  );
}

import { useState } from "react";
import { useUsageStream } from "@/hooks/useUsageStream";
import { Sidebar, type SectionKey } from "@/components/Sidebar";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { TrendChart } from "@/components/TrendChart";
import { SessionDetail } from "@/components/SessionDetail";
import { ProjectDetailSheet } from "@/components/ProjectDetailSheet";
import { ThemeToggle } from "@/components/ThemeToggle";
import { RoiView } from "@/components/RoiView";
import type { ProjectUsage } from "@/lib/api";
import { clientOf, groupProjectsByClient } from "@/lib/clients";

export default function App() {
  const [section, setSection] = useState<SectionKey>("all");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [clientFilter, setClientFilter] = useState<string | null>(null);
  const { sources, combined, connected } = useUsageStream();

  const projectsByClient = groupProjectsByClient(Object.keys(combined ?? {}));

  const handleSelectClient = (client: string | null) => {
    setClientFilter(client);
    if (client) setSection("all");
  };

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

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <Sidebar
        active={section}
        onSelect={setSection}
        projectsByClient={projectsByClient}
        activeClient={clientFilter}
        onSelectClient={handleSelectClient}
        onSelectProject={setSelectedProject}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-10 flex items-center justify-between px-6 h-16 border-b bg-background/80 backdrop-blur">
          <h1 className="text-lg font-semibold">{activeLabel}</h1>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                connected ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground"
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"}`} />
              {connected ? "En vivo" : "Conectando..."}
            </span>
            <ThemeToggle />
          </div>
        </header>
        <main key={section} className="flex-1 p-6 space-y-6 max-w-[1400px] w-full">
          {section === "roi" ? (
            <div className="dashboard-section" style={{ animationDelay: "0ms" }}>
              <RoiView sources={sources} />
            </div>
          ) : (
          <>
          <div className="dashboard-section" style={{ animationDelay: "0ms" }}>
            <TrendChart section={section} clientFilter={clientFilter} onSelectDate={setSelectedDate} />
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
        </main>
      </div>
      <ProjectDetailSheet
        sources={sources}
        section={section}
        project={selectedProject}
        onClose={() => setSelectedProject(null)}
      />
    </div>
  );
}

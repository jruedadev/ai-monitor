import { useState } from "react";
import { useUsageStream } from "@/hooks/useUsageStream";
import { Sidebar, type SectionKey } from "@/components/Sidebar";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { TrendChart } from "@/components/TrendChart";
import { SessionDetail } from "@/components/SessionDetail";
import { ThemeToggle } from "@/components/ThemeToggle";
import type { ProjectUsage } from "@/lib/api";

export default function App() {
  const [section, setSection] = useState<SectionKey>("all");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const { sources, combined, connected } = useUsageStream();

  const projectsForSection = (): Record<string, ProjectUsage> => {
    if (!sources || !combined) return {};
    if (section === "all") return combined;
    if (section === "openrouter") {
      const or = sources.openrouter;
      if (!or || or.unavailable || !or.models) return {};
      return Object.fromEntries(
        Object.entries(or.models).map(([model, v]) => [
          model,
          { total_tokens: v.tokens, cost: v.cost, messages: v.requests, session_count: v.requests, by_source: ["openrouter"] },
        ]),
      );
    }
    return Object.fromEntries(
      Object.entries(sources[section]).map(([name, v]) => [
        name,
        { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [section] },
      ]),
    );
  };

  const openRouterUnavailable = section === "openrouter" && sources?.openrouter?.unavailable;

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <Sidebar active={section} onSelect={setSection} />
      <main className="flex-1 p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">ai-monitor</h1>
          <div className="flex items-center gap-3">
            <span className={`text-xs ${connected ? "text-green-500" : "text-muted-foreground"}`}>
              {connected ? "● en vivo" : "○ conectando..."}
            </span>
            <ThemeToggle />
          </div>
        </div>
        <TrendChart onSelectDate={setSelectedDate} />
        {openRouterUnavailable ? (
          <div className="rounded-md border p-6 text-sm text-muted-foreground">
            OpenRouter no disponible
            {sources?.openrouter?.reason ? `: ${sources.openrouter.reason}` : "."}
          </div>
        ) : (
          combined && (
            <>
              <KpiCards projects={projectsForSection()} />
              <ProjectTable projects={projectsForSection()} />
              <SessionDetail
                sources={sources}
                section={section}
                selectedDate={selectedDate}
                onSelectDate={setSelectedDate}
              />
            </>
          )
        )}
      </main>
    </div>
  );
}

import { useState } from "react";
import { useUsageStream } from "@/hooks/useUsageStream";
import { Sidebar, type SectionKey } from "@/components/Sidebar";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { TrendChart } from "@/components/TrendChart";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function App() {
  const [section, setSection] = useState<SectionKey>("all");
  const { sources, combined, connected } = useUsageStream();

  const projectsForSection = () => {
    if (!sources || !combined) return {};
    if (section === "all") return combined;
    if (section === "openrouter") return {};
    return Object.fromEntries(
      Object.entries(sources[section]).map(([name, v]) => [
        name,
        { total_tokens: v.total_tokens, cost: v.cost, messages: v.messages, session_count: v.session_count, by_source: [section] },
      ]),
    );
  };

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
        <TrendChart />
        {combined && <KpiCards projects={projectsForSection()} />}
        {combined && <ProjectTable projects={projectsForSection()} />}
      </main>
    </div>
  );
}

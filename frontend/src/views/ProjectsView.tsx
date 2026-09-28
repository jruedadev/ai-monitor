import { Link, useLocation } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { KpiCards } from "@/components/KpiCards";
import { ProjectTable } from "@/components/ProjectTable";
import { SectionFallback } from "@/views/SectionFallback";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { groupProjectsByClient } from "@/lib/clients";
import { formatInt, formatUsd } from "@/lib/format";
import { projectsFor } from "@/lib/projects";
import { viewPath, withSource } from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";

interface ProjectsViewProps {
  client: string | null;
  source: SourceKey;
  sources: UsageSnapshot["sources"] | null;
  combined: Record<string, ProjectUsage> | null;
  onSelectProject: (project: string | null) => void;
}

export function ProjectsView({ client, source, sources, combined, onSelectProject }: ProjectsViewProps) {
  const { search } = useLocation();

  if (source === "openrouter") {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Proyectos</h1>
        <p className="text-sm text-muted-foreground">
          OpenRouter agrupa el consumo por modelo, no por proyecto.{" "}
          <Link to={withSource("/gasto", search)} className="text-link underline-offset-4 hover:underline">Ver gasto por modelo</Link>
        </p>
      </div>
    );
  }
  if (!combined) return <SectionFallback label="Cargando proyectos" />;

  if (client) {
    const projects = projectsFor(sources, combined, source, client);
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <Link to={withSource(viewPath("projects"), search)} className="inline-flex items-center gap-1 text-sm text-link hover:underline">
            <ChevronLeft className="h-4 w-4" aria-hidden /> Proyectos
          </Link>
          <h1 className="text-xl font-semibold">{client}</h1>
        </div>
        <KpiCards projects={projects} />
        <ProjectTable projects={projects} onSelectProject={onSelectProject} />
      </div>
    );
  }

  const all = projectsFor(sources, combined, source, null);
  const clients = Object.entries(groupProjectsByClient(Object.keys(all)))
    .map(([name, paths]) => ({ name, count: paths.length, cost: paths.reduce((sum, p) => sum + all[p].cost, 0) }))
    .sort((a, b) => b.cost - a.cost);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Proyectos</h1>
      {clients.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin proyectos para esta fuente.</p>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {clients.map((c) => (
            <li key={c.name}>
              <Link to={withSource(viewPath("projects", c.name), search)} className="card-interactive block rounded-xl border bg-card p-5">
                <p className="font-mono text-sm text-muted-foreground">{c.name}</p>
                <p className="mt-1 text-2xl font-bold tabular-nums">{formatUsd(c.cost)}</p>
                <p className="text-sm text-muted-foreground">{formatInt(c.count)} {c.count === 1 ? "proyecto" : "proyectos"}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

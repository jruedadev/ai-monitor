import { Link } from "react-router-dom";
import type { BriefingProject } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { PROJECT_PARAM, clientPath, withSource } from "@/lib/routes";
import { basename } from "@/lib/tree";

export function TopProjects({ projects, search }: { projects: BriefingProject[]; search: string }) {
  return (
    <section aria-labelledby="top-projects-title" className="rounded-xl border bg-card p-5">
      <h2 id="top-projects-title" className="text-sm font-medium">Proyectos con más gasto</h2>
      {projects.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Sin gasto por proyecto en este periodo</p>
      ) : (
        <ol className="mt-4 space-y-3">
          {projects.map((p) => {
            const pct = Math.round(p.share * 100);
            const params = new URLSearchParams();
            params.set(PROJECT_PARAM, p.project);
            const href = `${clientPath(p.client)}?${params}`;
            return (
              <li key={p.project}>
                <Link to={withSource(href, search)} className="-m-2 block rounded-lg p-2 hover:bg-muted">
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate font-medium" title={p.project}>{basename(p.project)}</span>
                    <span className="shrink-0 tabular-nums">{formatUsd(p.cost)}</span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="h-1.5 flex-1 rounded-full bg-muted" aria-hidden>
                      <div className="h-full rounded-full bg-muted-foreground/70" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">{pct} %</span>
                  </div>
                  <p className="mt-0.5 font-mono text-xs text-muted-foreground">{p.client}</p>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

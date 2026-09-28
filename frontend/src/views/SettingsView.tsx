import { SettingsForm } from "@/components/SettingsForm";
import { EngineSettingsForm } from "@/components/EngineSettingsForm";
import { Skeleton } from "@/components/ui/skeleton";
import type { UsageSnapshot } from "@/lib/api";
import { sourceStatuses } from "@/lib/settings";
import { SOURCE_META } from "@/lib/sources";

const STATE_LABEL = { data: "Con datos", empty: "Sin datos", unavailable: "No disponible" } as const;

export function SettingsView({ sources }: { sources: UsageSnapshot["sources"] | null }) {
  const statuses = sourceStatuses(sources);
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Configuración</h1>
      <SettingsForm />
      <EngineSettingsForm />
      <section aria-labelledby="sources-title" className="rounded-xl border bg-card p-5">
        <h2 id="sources-title" className="text-sm font-medium">Fuentes</h2>
        {statuses.length === 0 ? (
          <Skeleton className="mt-3 h-40 w-full" />
        ) : (
          <ul className="mt-3 divide-y">
            {statuses.map((s) => {
              const Icon = SOURCE_META[s.key].icon;
              return (
                <li key={s.key} className="flex items-center gap-3 py-2.5">
                  <Icon className="h-4 w-4 shrink-0" style={{ color: SOURCE_META[s.key].color }} aria-hidden />
                  <span className="text-sm font-medium">{s.label}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground" title={s.detail}>{s.detail}</span>
                  <span className="shrink-0 rounded-full border px-2 py-0.5 text-xs">{STATE_LABEL[s.state]}</span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

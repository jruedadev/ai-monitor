import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { SourceChip } from "@/components/SourceChip";
import { SectionFallback } from "@/views/SectionFallback";
import type { UsageSnapshot } from "@/lib/api";
import { LIVE_SOURCES, mergeOfficeAgents, type ActivitySnapshot } from "@/lib/activity";
import type { OfficeAgent } from "@/lib/office";

// El motor Canvas va en su propio chunk: solo se descarga al abrir la oficina.
const OfficeStage = lazy(() => import("@/pixel/OfficeStage"));

const SOURCE_LABEL: Record<(typeof LIVE_SOURCES)[number], string> = {
  claude_code: "Claude Code",
  opencode: "OpenCode",
  hermes: "Hermes",
};

export function statusText(agent: OfficeAgent, nowMs: number): string {
  switch (agent.state) {
    case "tool":
      if (agent.toolKind === "run") return `ejecutando ${agent.tool}`;
      if (agent.toolKind === "edit") return "editando";
      if (agent.toolKind === "read") return "leyendo";
      return `usando ${agent.tool}`;
    case "waiting":
      return `esperando · ${Math.max(0, Math.round((nowMs - agent.sinceMs) / 1000))} s`;
    case "thinking":
      return "pensando";
    default:
      return "en pausa";
  }
}

interface OfficeViewProps {
  sources: UsageSnapshot["sources"] | null;
  activity: ActivitySnapshot | null;
  onSelectProject: (project: string | null) => void;
}

export function OfficeView({ sources, activity, onSelectProject }: OfficeViewProps) {
  const [now, setNow] = useState(() => Date.now());
  const agents = useMemo(() => mergeOfficeAgents(activity, sources, now), [activity, sources, now]);
  const anyWaiting = agents.some((a) => a.state === "waiting");

  // Cada segundo mientras haya un agente esperando (contador de segundos); si no, cada 15 s.
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), anyWaiting ? 1_000 : 15_000);
    return () => window.clearInterval(timer);
  }, [anyWaiting]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Oficina</h1>
        <p className="text-sm text-muted-foreground">Actividad en vivo de las sesiones de los últimos 30 min.</p>
      </div>
      <Suspense fallback={<SectionFallback label="Cargando oficina" />}>
        <OfficeStage agents={agents} onSelect={(a) => onSelectProject(a.project)} />
      </Suspense>
      {agents.length === 0 ? (
        <p className="text-sm text-muted-foreground">La oficina está vacía: ninguna sesión reciente.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <li key={a.key}>
              <button
                type="button"
                onClick={() => onSelectProject(a.project)}
                className="flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm hover:bg-muted"
              >
                <span className="truncate font-medium">{a.label}</span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{statusText(a, now)}</span>
                  <SourceChip source={a.source} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted-foreground">
        En vivo:{" "}
        {LIVE_SOURCES.map((s, i) => (
          <span key={s}>
            {i > 0 && " · "}
            {SOURCE_LABEL[s]}
            {activity?.sources[s] === "ok" ? "" : " (no disponible)"}
          </span>
        ))}
        {" · "}Codex: estado básico
      </p>
    </div>
  );
}

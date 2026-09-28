import { Suspense, lazy } from "react";
import { SessionDetail } from "@/components/SessionDetail";
import { SectionFallback } from "@/views/SectionFallback";
import type { UsageSnapshot } from "@/lib/api";
import type { SourceKey } from "@/lib/sources";

const TrendChart = lazy(() => import("@/components/TrendChart").then((m) => ({ default: m.TrendChart })));

interface ActivityViewProps {
  source: SourceKey;
  sources: UsageSnapshot["sources"] | null;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onSelectProject: (project: string | null) => void;
}

export function ActivityView({ source, sources, selectedDate, onSelectDate, onSelectProject }: ActivityViewProps) {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Actividad</h1>
      <Suspense fallback={<SectionFallback label="Cargando tendencia" />}>
        <TrendChart section={source} selectedDate={selectedDate} onSelectDate={onSelectDate} />
      </Suspense>
      <SessionDetail
        sources={sources}
        section={source}
        clientFilter={null}
        selectedDate={selectedDate}
        onSelectDate={onSelectDate}
        onSelectProject={onSelectProject}
      />
    </div>
  );
}

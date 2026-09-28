import { useId } from "react";
import type { BriefingResponse } from "@/lib/api";
import { coverageLabel, windowLabel } from "@/lib/briefing";
import { formatMonth } from "@/lib/format";

interface BriefingHeaderProps {
  briefing: BriefingResponse;
  onCompareChange: (month: string | null) => void;
}

export function BriefingHeader({ briefing, onCompareChange }: BriefingHeaderProps) {
  const selectId = useId();
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight">{formatMonth(briefing.window.month)}</h1>
        <p className="text-sm text-muted-foreground">{windowLabel(briefing)}</p>
      </div>
      {briefing.eligible_months.length > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor={selectId} className="text-muted-foreground">Comparar con</label>
          <select
            id={selectId}
            value={briefing.compare.month}
            onChange={(e) => onCompareChange(e.target.value)}
            className="max-w-[16rem] rounded-lg border bg-background px-3 py-1.5 text-sm"
          >
            {briefing.eligible_months.map((m) => (
              <option key={m.month} value={m.month}>
                {formatMonth(m.month)}
                {m.coverage === "partial" && m.since ? ` · ${coverageLabel(m.since)}` : ""}
              </option>
            ))}
          </select>
        </div>
      )}
    </header>
  );
}

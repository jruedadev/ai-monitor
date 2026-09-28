import { SOURCE_KEYS, SOURCE_META, type SourceKey } from "@/lib/sources";
import { cn } from "@/lib/utils";

const OPTIONS = SOURCE_KEYS.map((key) => ({ key, label: key === "all" ? "Todas" : SOURCE_META[key].label }));

interface SourceFilterProps {
  value: SourceKey;
  onChange: (source: SourceKey) => void;
}

/** Chips en escritorio; select compacto en pantallas angostas (spec §4.5). */
export function SourceFilter({ value, onChange }: SourceFilterProps) {
  return (
    <>
      <div role="group" aria-label="Filtrar por fuente" className="hidden items-center gap-1 xl:flex">
        {OPTIONS.map((o) => (
          <button
            key={o.key}
            type="button"
            aria-pressed={value === o.key}
            onClick={() => onChange(o.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
              value === o.key ? "border-primary bg-primary/10 font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {o.key !== "all" && <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: SOURCE_META[o.key].color }} />}
            {o.label}
          </button>
        ))}
      </div>
      <label className="xl:hidden">
        <span className="sr-only">Filtrar por fuente</span>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as SourceKey)}
          className="max-w-[9.5rem] rounded-lg border bg-background px-2 py-1.5 text-sm"
        >
          {OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </select>
      </label>
    </>
  );
}

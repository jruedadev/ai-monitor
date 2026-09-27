import { SOURCE_META } from "@/lib/sources";

/** Chip de fuente: el texto va en tinta (no en el color de la serie, que no
 * alcanza 4.5:1 en modo claro para aqua/yellow) y la identidad la lleva el punto. */
export function SourceChip({ source }: { source: string }) {
  const meta = SOURCE_META[source];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium text-foreground whitespace-nowrap">
      <span
        aria-hidden
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: meta?.color ?? "var(--muted-foreground)" }}
      />
      {meta?.label ?? source}
    </span>
  );
}

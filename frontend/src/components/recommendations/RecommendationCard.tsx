// frontend/src/components/recommendations/RecommendationCard.tsx
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Check, Copy, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SourceChip } from "@/components/SourceChip";
import type { Recommendation, UserStatus } from "@/lib/api";
import { IMPACT_LABEL, KIND_LABEL, evidenceLines, isCostEvidence } from "@/lib/recommendations";
import { withSource } from "@/lib/routes";
import { cn } from "@/lib/utils";

const IMPACT_CLASS = {
  alto: "border-amber-500/40 text-amber-700 dark:text-amber-400",
  medio: "border-link/40 text-link",
  bajo: "text-muted-foreground",
} as const;

interface Props {
  rec: Recommendation;
  onStatus: (status: UserStatus) => void;
}

export function RecommendationCard({ rec, onStatus }: Props) {
  const { search } = useLocation();
  const [copied, setCopied] = useState(false);
  const ev = rec.evidence;
  const sources = rec.tool === "varias" ? ev.sources : [rec.tool];

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(rec.draft);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("No se pudo copiar el borrador:", err);
    }
  };

  return (
    <article aria-labelledby={`rec-${rec.id}`} className="min-w-0 space-y-3 rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-muted px-2 py-0.5 font-medium">{KIND_LABEL[rec.kind]}</span>
        <span className={cn("rounded-full border px-2 py-0.5", IMPACT_CLASS[rec.impact])}>{IMPACT_LABEL[rec.impact]}</span>
        {sources.map((s) => <SourceChip key={s} source={s} />)}
      </div>
      <h2 id={`rec-${rec.id}`} className="break-words text-base font-semibold">{rec.pattern}</h2>
      <p className="break-words text-sm text-muted-foreground">{rec.description}</p>

      <details className="text-sm">
        <summary className="cursor-pointer select-none font-medium">Evidencia</summary>
        <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
          {evidenceLines(rec).map((line) => <li key={line} className="break-words">{line}</li>)}
        </ul>
        {!isCostEvidence(ev) && ev.snippets.length > 0 && (
          <ul className="mt-2 space-y-1">
            {ev.snippets.map((s) => (
              <li key={s} className="break-words border-l-2 pl-2 text-xs italic text-muted-foreground">“{s}”</li>
            ))}
          </ul>
        )}
        {isCostEvidence(ev) && (
          <Link to={withSource(ev.link, search)} className="mt-2 inline-block text-xs text-link underline-offset-4 hover:underline">
            Ver en el dashboard
          </Link>
        )}
      </details>

      <div className="relative">
        <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap break-words rounded-lg bg-muted p-3 pr-24 text-xs">
          <code>{rec.draft}</code>
        </pre>
        <Button size="sm" variant="outline" onClick={copy} className="absolute right-2 top-2">
          {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {rec.status === "nueva" && (
          <>
            <Button size="sm" onClick={() => onStatus("aplicada")}>Aplicar<span className="sr-only">: {rec.pattern}</span></Button>
            <Button size="sm" variant="outline" onClick={() => onStatus("saltada")}>Saltar<span className="sr-only">: {rec.pattern}</span></Button>
          </>
        )}
        {(rec.status === "aplicada" || rec.status === "saltada") && (
          <Button size="sm" variant="outline" onClick={() => onStatus("nueva")}>
            <Undo2 aria-hidden />Deshacer<span className="sr-only">: {rec.pattern}</span>
          </Button>
        )}
      </div>
    </article>
  );
}
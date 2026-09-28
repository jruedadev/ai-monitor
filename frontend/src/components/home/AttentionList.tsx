import { Link } from "react-router-dom";
import { AlertTriangle, Info } from "lucide-react";
import type { BriefingSignal } from "@/lib/api";
import { withSource } from "@/lib/routes";

// El color nunca es el único indicador: punto + ícono + texto accesible.
const SEVERITY = {
  warning: { icon: AlertTriangle, label: "Advertencia", dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-400" },
  info: { icon: Info, label: "Información", dot: "bg-link", text: "text-link" },
} as const;

export function AttentionList({ signals, search }: { signals: BriefingSignal[]; search: string }) {
  return (
    <section aria-labelledby="attention-title" className="rounded-xl border bg-card p-5">
      <h2 id="attention-title" className="text-sm font-medium">Atención ahora</h2>
      {signals.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Nada requiere tu atención ahora</p>
      ) : (
        <ul className="mt-3 divide-y">
          {signals.map((signal) => {
            const meta = SEVERITY[signal.severity];
            return (
              <li key={signal.id} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                <span className={`mt-0.5 inline-flex shrink-0 items-center gap-1.5 ${meta.text}`}>
                  <span aria-hidden className={`h-2 w-2 rounded-full ${meta.dot}`} />
                  <meta.icon className="h-4 w-4" aria-hidden />
                  <span className="sr-only">{meta.label}:</span>
                </span>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-sm font-medium">{signal.title}</p>
                  <ul className="space-y-0.5 text-xs text-muted-foreground">
                    {signal.evidence.map((item) => (
                      <li key={item} className="break-words">{item}</li>
                    ))}
                  </ul>
                </div>
                <Link
                  to={withSource(signal.link, search)}
                  className="shrink-0 self-center text-sm text-link underline-offset-4 hover:underline"
                >
                  Ver<span className="sr-only">: {signal.title}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

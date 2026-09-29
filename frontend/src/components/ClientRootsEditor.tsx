import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MAX_CLIENT_ROOTS, previewClients, type ClientRoot, type ClientRootMode } from "@/lib/clients";

const MODE_OPTIONS: { value: ClientRootMode; label: string }[] = [
  { value: "cliente", label: "La carpeta siguiente es el cliente" },
  { value: "plano", label: "Todo lo de dentro es un solo cliente" },
];

interface ClientRootsEditorProps {
  roots: ClientRoot[];
  onChange: (roots: ClientRoot[]) => void;
  /** Rutas de proyecto conocidas, para la vista previa. */
  paths: string[];
}

/** Editor controlado de raíces (nombre de carpeta o ruta absoluta + modo). La primera que coincide gana. */
export function ClientRootsEditor({ roots, onChange, paths }: ClientRootsEditorProps) {
  const set = (i: number, next: Partial<ClientRoot>) => onChange(roots.map((r, j) => (j === i ? { ...r, ...next } : r)));
  const move = (i: number, delta: -1 | 1) => {
    const next = [...roots];
    [next[i], next[i + delta]] = [next[i + delta], next[i]];
    onChange(next);
  };
  const preview = previewClients(paths, roots);

  return (
    <div className="space-y-4">
      <ol className="space-y-2">
        {roots.map((r, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2">
            <input
              aria-label={`Raíz ${i + 1}`}
              value={r.root}
              onChange={(e) => set(i, { root: e.target.value })}
              placeholder="DEV o /ruta/absoluta"
              spellCheck={false}
              className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-2 font-mono text-sm"
            />
            <select
              aria-label={`Modo de la raíz ${i + 1}`}
              value={r.mode}
              onChange={(e) => set(i, { mode: e.target.value as ClientRootMode })}
              className="rounded-lg border bg-background px-2 py-2 text-sm"
            >
              {MODE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <Button variant="ghost" size="icon-sm" aria-label="Subir" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp aria-hidden /></Button>
            <Button variant="ghost" size="icon-sm" aria-label="Bajar" disabled={i === roots.length - 1} onClick={() => move(i, 1)}><ArrowDown aria-hidden /></Button>
            <Button variant="ghost" size="icon-sm" aria-label="Quitar" disabled={roots.length === 1} onClick={() => onChange(roots.filter((_, j) => j !== i))}><Trash2 aria-hidden /></Button>
          </li>
        ))}
      </ol>
      <Button
        variant="outline"
        size="sm"
        disabled={roots.length >= MAX_CLIENT_ROOTS}
        onClick={() => onChange([...roots, { root: "", mode: "cliente" }])}
      >
        <Plus aria-hidden />Añadir raíz
      </Button>
      <div aria-live="polite" className="rounded-lg border bg-muted/40 p-3 text-sm">
        {paths.length === 0 ? (
          <p className="text-muted-foreground">Aún no hay proyectos detectados; la agrupación se aplicará cuando los haya.</p>
        ) : (
          <>
            <p className="font-medium">Así quedarían tus {paths.length} proyectos:</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {preview.clients.map((c) => (
                <li key={c.name} className="rounded-full border px-2 py-0.5 text-xs">{c.name} · {c.count}</li>
              ))}
            </ul>
            {preview.other > 0 && <p className="mt-2 text-xs text-muted-foreground">{preview.other} en «Otros» (no coinciden con ninguna raíz).</p>}
          </>
        )}
      </div>
    </div>
  );
}

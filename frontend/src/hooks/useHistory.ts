import { useCallback, useEffect, useState } from "react";
import { fetchHistory, type HistoryResponse } from "@/lib/api";

/** El historial es un rollup diario: con refrescarlo cada pocos minutos basta.
 * La caché a nivel de módulo evita volver a pedirlo en cada cambio de sección
 * (App re-monta el contenido con `key={section}` para la animación de entrada). */
const CACHE_TTL_MS = 5 * 60_000;
const cache = new Map<number, { at: number; promise: Promise<HistoryResponse>; data?: HistoryResponse }>();

function freshData(days: number): HistoryResponse | undefined {
  const hit = cache.get(days);
  return hit && Date.now() - hit.at < CACHE_TTL_MS ? hit.data : undefined;
}

function loadHistory(days: number, force: boolean): Promise<HistoryResponse> {
  const hit = cache.get(days);
  if (!force && hit && Date.now() - hit.at < CACHE_TTL_MS) return hit.promise;
  const entry: { at: number; promise: Promise<HistoryResponse>; data?: HistoryResponse } = {
    at: Date.now(),
    promise: fetchHistory(days),
  };
  cache.set(days, entry);
  const { promise } = entry;
  promise.then((data) => { entry.data = data; }, () => {});
  // Un fallo no debe quedar cacheado: el siguiente intento vuelve a pedirlo.
  promise.catch(() => cache.delete(days));
  return promise;
}

export type HistoryState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: HistoryResponse };

export function useHistory(days: number): HistoryState & { retry: () => void } {
  // Con datos frescos en caché se pinta de inmediato, sin parpadeo de skeleton.
  const [state, setState] = useState<HistoryState>(() => {
    const data = freshData(days);
    return data ? { status: "ready", data } : { status: "loading" };
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const cached = attempt === 0 ? freshData(days) : undefined;
    if (cached) {
      setState({ status: "ready", data: cached });
      return;
    }
    setState({ status: "loading" });
    loadHistory(days, attempt > 0)
      .then((data) => !cancelled && setState({ status: "ready", data }))
      .catch((err: Error) => !cancelled && setState({ status: "error", message: err.message }));
    return () => { cancelled = true; };
  }, [days, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}

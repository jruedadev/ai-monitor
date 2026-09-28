import { useCallback, useEffect, useState } from "react";
import { HttpError, fetchBriefing, type BriefingResponse } from "@/lib/api";
import type { SourceKey } from "@/lib/sources";

/** Caché por (fuente, mes comparado): volver al Inicio o a un filtro ya visto pinta
 * de inmediato, sin skeleton, mientras se revalida en segundo plano. */
const cache = new Map<string, BriefingResponse>();

export type BriefingState =
  | { status: "loading" }
  | { status: "error"; message: string; httpStatus: number | null }
  | { status: "ready"; data: BriefingResponse };

/** `refreshKey` cambia con cada snapshot SSE nuevo: dispara una revalidación silenciosa. */
export function useBriefing(
  source: SourceKey, compare: string | null, refreshKey: unknown,
): BriefingState & { retry: () => void } {
  const key = `${source}|${compare ?? ""}`;
  const [state, setState] = useState<BriefingState>(() => {
    const data = cache.get(key);
    return data ? { status: "ready", data } : { status: "loading" };
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const cached = cache.get(key);
    setState(cached ? { status: "ready", data: cached } : { status: "loading" });
    fetchBriefing(source, compare)
      .then((data) => {
        cache.set(key, data);
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err: Error) => {
        // Con datos en pantalla, un fallo de revalidación no los reemplaza por un error.
        if (cancelled || cached) return;
        setState({ status: "error", message: err.message, httpStatus: err instanceof HttpError ? err.status : null });
      });
    return () => {
      cancelled = true;
    };
  }, [key, source, compare, refreshKey, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}

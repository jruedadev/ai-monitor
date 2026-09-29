import { useCallback, useEffect, useState } from "react";
import { fetchRecommendations, type RecommendationStatus, type RecommendationsResponse } from "@/lib/api";

export type RecommendationsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: RecommendationsResponse };

export function useRecommendations(tab: RecommendationStatus, refreshKey: unknown) {
  const [state, setState] = useState<RecommendationsState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchRecommendations(tab)
      .then((data) => !cancelled && setState({ status: "ready", data }))
      .catch((err: Error) => {
        if (!cancelled) setState((prev) => (prev.status === "ready" ? prev : { status: "error", message: err.message }));
      });
    return () => {
      cancelled = true;
    };
  }, [tab, refreshKey, attempt]);

  useEffect(() => setState({ status: "loading" }), [tab]);

  const update = useCallback(
    (fn: (data: RecommendationsResponse) => RecommendationsResponse) =>
      setState((prev) => (prev.status === "ready" ? { status: "ready", data: fn(prev.data) } : prev)),
    [],
  );
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, update, retry };
}

export function useNewRecommendationsCount(refreshKey: unknown): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let cancelled = false;
    fetchRecommendations("nueva")
      .then((data) => !cancelled && setCount(data.recommendations.length))
      .catch(() => !cancelled && setCount(0));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);
  return count;
}
import { useEffect, useRef, useState } from "react";
import type { UsageSnapshot } from "@/lib/api";
import { fetchActivity, type ActivitySnapshot } from "@/lib/activity";

export function useUsageStream() {
  const [snapshot, setSnapshot] = useState<UsageSnapshot | null>(null);
  const [activity, setActivity] = useState<ActivitySnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [recommendationsVersion, setRecommendationsVersion] = useState(0);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/stream");
    sourceRef.current = es;
    let alive = true;

    es.addEventListener("usage", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as UsageSnapshot;
      setSnapshot(data);
      setConnected(true);
    });

    es.addEventListener("activity", (event) => {
      setActivity(JSON.parse((event as MessageEvent).data) as ActivitySnapshot);
    });

    es.addEventListener("recommendations", () => setRecommendationsVersion((n) => n + 1));

    es.onerror = () => setConnected(false);

    // Snapshot inicial: si falla queda null hasta el primer evento SSE (sin romper la vista).
    void fetchActivity().then((snap) => {
      if (alive && snap) setActivity((prev) => prev ?? snap);
    });

    return () => {
      alive = false;
      es.close();
    };
  }, []);

  return {
    sources: snapshot?.sources ?? null,
    combined: snapshot?.combined ?? null,
    activity,
    connected,
    recommendationsVersion,
  };
}

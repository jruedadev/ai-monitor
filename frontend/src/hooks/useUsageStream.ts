import { useEffect, useRef, useState } from "react";
import type { UsageSnapshot } from "@/lib/api";

export function useUsageStream() {
  const [snapshot, setSnapshot] = useState<UsageSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/stream");
    sourceRef.current = es;

    es.addEventListener("usage", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as UsageSnapshot;
      setSnapshot(data);
      setConnected(true);
    });

    es.onerror = () => setConnected(false);

    return () => es.close();
  }, []);

  return {
    sources: snapshot?.sources ?? null,
    combined: snapshot?.combined ?? null,
    connected,
  };
}

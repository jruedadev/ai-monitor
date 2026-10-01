/**
 * Escenario de la oficina: monta el motor Canvas de Pixel Agents (MIT, ver LICENSE)
 * y sincroniza sus personajes con los agentes de la oficina (actividad en vivo + estado básico). Sin editor,
 * sin sonido y sin transporte: el original recibía todo por mensajes de VS Code.
 */
import { useEffect, useRef, useState } from "react";
import type { OfficeAgent } from "@/lib/office";
import { engineStateKey, toEngineState } from "./engineState";
import { fitZoom } from "./fitZoom";
import { loadOfficeAssets } from "./loadAssets";
import { trimLayout } from "./trimLayout";
import { OfficeCanvas } from "./office/components/OfficeCanvas";
import { EditorState } from "./office/editor/editorState";
import { OfficeState } from "./office/engine/officeState";

const ASSET_BASE = `${import.meta.env.BASE_URL}pixel/`;
const noop = () => {};

interface OfficeStageProps {
  agents: OfficeAgent[];
  onSelect: (agent: OfficeAgent) => void;
}

export default function OfficeStage({ agents, onSelect }: OfficeStageProps) {
  const [office] = useState(() => new OfficeState());
  const [editor] = useState(() => new EditorState());
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [zoom, setZoom] = useState(2);
  const panRef = useRef({ x: 0, y: 0 });
  // key de sesión ↔ id numérico del motor; estable mientras la vista esté montada.
  const ids = useRef(new Map<string, number>());
  const nextId = useRef(1);
  const applied = useRef(new Map<number, string>());
  const containerRef = useRef<HTMLDivElement>(null);
  const layoutSize = useRef({ cols: 0, rows: 0 });

  useEffect(() => {
    let cancelled = false;
    loadOfficeAssets(ASSET_BASE)
      .then(({ layout }) => {
        if (cancelled) return;
        if (layout) {
          const trimmed = trimLayout(layout);
          layoutSize.current = { cols: trimmed.cols, rows: trimmed.rows };
          office.rebuildFromLayout(trimmed);
        }
        setStatus("ready");
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, [office]);

  useEffect(() => {
    if (status !== "ready") return;
    const present = new Set<string>();
    for (const agent of agents) {
      present.add(agent.key);
      let id = ids.current.get(agent.key);
      if (id === undefined) {
        id = nextId.current++;
        ids.current.set(agent.key, id);
        office.addAgent(id, undefined, undefined, undefined, false, agent.label);
      }
      const next = toEngineState(agent);
      const key = engineStateKey(next);
      if (applied.current.get(id) === key) continue;
      applied.current.set(id, key);
      office.setAgentActive(id, next.active);
      office.setAgentTool(id, next.tool);
      if (next.waiting) office.showWaitingBubble(id);
    }
    for (const [key, id] of ids.current) {
      if (present.has(key)) continue;
      office.removeAgent(id);
      ids.current.delete(key);
      applied.current.delete(id);
    }
  }, [agents, office, status]);

  useEffect(() => {
    if (status !== "ready" || !containerRef.current) return;
    const el = containerRef.current;
    const refit = () => {
      const { cols, rows } = layoutSize.current;
      const dpr = window.devicePixelRatio || 1;
      const z = fitZoom(el.clientWidth, el.clientHeight, cols, rows, dpr);
      setZoom(z);
      const fits = cols * 16 * z <= el.clientWidth * dpr && rows * 16 * z <= el.clientHeight * dpr;
      if (fits) panRef.current = { x: 0, y: 0 }; // si cabe, el pan se fija en 0; si no, se arrastra
    };
    refit();
    const ro = new ResizeObserver(refit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [status]);

  const handleClick = (id: number) => {
    for (const [key, agentId] of ids.current) {
      if (agentId !== id) continue;
      const agent = agents.find((a) => a.key === key);
      if (agent) onSelect(agent);
    }
  };

  if (status === "error") {
    return <p className="p-6 text-sm text-muted-foreground">No se pudieron cargar los gráficos de la oficina.</p>;
  }
  return (
    <div ref={containerRef} className="relative h-[60vh] min-h-[360px] w-full overflow-hidden rounded-lg border bg-muted/30" aria-busy={status === "loading"}>
      {status === "ready" && (
        <OfficeCanvas
          officeState={office}
          onClick={handleClick}
          isEditMode={false}
          editorState={editor}
          onEditorTileAction={noop}
          onEditorEraseAction={noop}
          onEditorSelectionChange={noop}
          onDeleteSelected={noop}
          onRotateSelected={noop}
          onDragMove={noop}
          editorTick={0}
          zoom={zoom}
          onZoomChange={setZoom}
          panRef={panRef}
          showAreas={false}
          activeAreaLabel={null}
        />
      )}
    </div>
  );
}

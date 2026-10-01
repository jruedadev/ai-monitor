import type { OfficeAgent } from "@/lib/office";

export interface EngineState {
  active: boolean;
  tool: "Read" | "Edit" | null;
  waiting: boolean;
}

/** Tabla de §5.2 del spec: estado de actividad → llamadas a OfficeState. */
export function toEngineState(agent: Pick<OfficeAgent, "state" | "toolKind">): EngineState {
  switch (agent.state) {
    case "tool":
    case "waiting":
      return { active: true, tool: agent.toolKind === "read" ? "Read" : "Edit", waiting: agent.state === "waiting" };
    case "thinking":
      return { active: true, tool: "Edit", waiting: false };
    default:
      return { active: false, tool: null, waiting: false };
  }
}

/** Clave estable: solo cambia si hay que volver a llamar al motor (evita reiniciar animaciones). */
export const engineStateKey = (s: EngineState): string => `${s.active}|${s.tool}|${s.waiting}`;

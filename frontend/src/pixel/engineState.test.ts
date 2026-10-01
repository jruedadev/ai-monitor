import { describe, expect, it } from "vitest";
import { engineStateKey, toEngineState } from "@/pixel/engineState";

describe("toEngineState", () => {
  it("tool: activo; read → Read, el resto → Edit", () => {
    expect(toEngineState({ state: "tool", toolKind: "read" })).toEqual({ active: true, tool: "Read", waiting: false });
    for (const kind of ["edit", "run", "other", null] as const) {
      expect(toEngineState({ state: "tool", toolKind: kind })).toEqual({ active: true, tool: "Edit", waiting: false });
    }
  });
  it("waiting: igual que tool más la burbuja", () => {
    expect(toEngineState({ state: "waiting", toolKind: "run" })).toEqual({ active: true, tool: "Edit", waiting: true });
    expect(toEngineState({ state: "waiting", toolKind: "read" })).toEqual({ active: true, tool: "Read", waiting: true });
  });
  it("thinking: activo con Edit; idle: inactivo", () => {
    expect(toEngineState({ state: "thinking", toolKind: null })).toEqual({ active: true, tool: "Edit", waiting: false });
    expect(toEngineState({ state: "idle", toolKind: null })).toEqual({ active: false, tool: null, waiting: false });
  });
  it("la clave solo cambia cuando cambia el estado o la clase del agente", () => {
    const a = engineStateKey(toEngineState({ state: "tool", toolKind: "run" }));
    const b = engineStateKey(toEngineState({ state: "tool", toolKind: "other" })); // misma animación
    const c = engineStateKey(toEngineState({ state: "tool", toolKind: "read" }));
    expect(a).toBe(b);
    expect(a).not.toBe(c);
  });
});

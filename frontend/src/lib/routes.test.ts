import { describe, expect, it } from "vitest";
import { clientPath, parsePath, sectionPath, SECTION_KEYS } from "@/lib/routes";
import { withSource } from "@/lib/routes";

describe("parsePath", () => {
  it("raíz = vista general", () => {
    expect(parsePath("/")).toEqual({ section: "all", client: null });
  });

  it("slug de fuente → clave de sección", () => {
    expect(parsePath("/claude-code")).toEqual({ section: "claude_code", client: null });
    expect(parsePath("/roi")).toEqual({ section: "roi", client: null });
  });

  it("cliente decodifica caracteres especiales", () => {
    expect(parsePath("/cliente/Mi%20Cliente")).toEqual({ section: "all", client: "Mi Cliente" });
  });

  it("rutas desconocidas → null", () => {
    expect(parsePath("/claude_code")).toBeNull();
    expect(parsePath("/cliente")).toBeNull();
    expect(parsePath("/cliente/a/b")).toBeNull();
  });
});

describe("ida y vuelta", () => {
  it.each(SECTION_KEYS)("sectionPath(%s) se vuelve a parsear igual", (key) => {
    expect(parsePath(sectionPath(key))).toEqual({ section: key, client: null });
  });

  it("clientPath se vuelve a parsear igual", () => {
    expect(parsePath(clientPath("A/B & C"))).toEqual({ section: "all", client: "A/B & C" });
  });
});

describe("withSource", () => {
  it("conserva ?fuente= de la URL actual y no pisa uno explícito", () => {
    expect(withSource("/actividad?dia=2026-09-27", "?fuente=codex&dia=2026-01-01")).toBe("/actividad?dia=2026-09-27&fuente=codex");
    expect(withSource("/gasto?fuente=claude-code", "?fuente=codex")).toBe("/gasto?fuente=claude-code");
    expect(withSource("/configuracion", "")).toBe("/configuracion");
  });
});

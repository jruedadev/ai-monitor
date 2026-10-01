import { describe, expect, it } from "vitest";
import {
  VIEW_KEYS, legacyRedirect, parsePath, parseSource, promptPath, searchForSource, sourceSlug, viewPath, withSource,
} from "@/lib/routes";
import { SOURCE_KEYS } from "@/lib/sources";

describe("parsePath", () => {
  it("vistas nuevas", () => {
    expect(parsePath("/")).toEqual({ view: "home", client: null });
    expect(parsePath("/bienvenida")).toEqual({ view: "onboarding", client: null });
    expect(parsePath("/actividad")).toEqual({ view: "activity", client: null });
    expect(parsePath("/gasto")).toEqual({ view: "spend", client: null });
    expect(parsePath("/gasto/roi")).toEqual({ view: "roi", client: null });
    expect(parsePath("/proyectos")).toEqual({ view: "projects", client: null });
    expect(parsePath("/proyectos/Mi%20Cliente")).toEqual({ view: "projects", client: "Mi Cliente" });
    expect(parsePath("/recomendaciones")).toEqual({ view: "recommendations", client: null });
    expect(parsePath("/configuracion")).toEqual({ view: "settings", client: null });
    expect(parsePath("/oficina")).toEqual({ view: "office", client: null });
    expect(viewPath("office")).toBe("/oficina");
  });

  it("rutas desconocidas o mal codificadas → null", () => {
    expect(parsePath("/bienvenida/otra")).toBeNull();
    expect(parsePath("/gasto/otra")).toBeNull();
    expect(parsePath("/proyectos/a/b")).toBeNull();
    expect(parsePath("/claude-code")).toBeNull();
    expect(parsePath("/proyectos/%E0%A4%A")).toBeNull();
    expect(parsePath("/recomendaciones/otra")).toBeNull();
  });

  it.each(VIEW_KEYS)("viewPath(%s) ida y vuelta", (view) => {
    expect(parsePath(viewPath(view))).toEqual({ view, client: null });
  });

  it("viewPath de cliente ida y vuelta", () => {
    expect(parsePath(viewPath("projects", "A/B & C"))).toEqual({ view: "projects", client: "A/B & C" });
  });
});

describe("fuente como parámetro", () => {
  it.each(SOURCE_KEYS)("parseSource(sourceSlug(%s)) ida y vuelta", (key) => {
    expect(parseSource(sourceSlug(key))).toBe(key);
  });
  it("slug desconocido o ausente → all", () => {
    expect(parseSource(null)).toBe("all");
    expect(parseSource("claude_code")).toBe("all");
  });
  it("cambiar la fuente limpia comparar y día, y conserva el resto", () => {
    expect(searchForSource("?comparar=2026-07&dia=2026-09-01&proyecto=%2Fa", "codex")).toBe("proyecto=%2Fa&fuente=codex");
    expect(searchForSource("?fuente=codex", "all")).toBe("");
  });
});

describe("redirecciones legadas", () => {
  it("fuentes → /gasto?fuente=", () => {
    expect(legacyRedirect("/claude-code", "")).toBe("/gasto?fuente=claude-code");
    expect(legacyRedirect("/openrouter", "?dia=2026-09-01")).toBe("/gasto?dia=2026-09-01&fuente=openrouter");
  });
  it("roi y cliente conservan la query", () => {
    expect(legacyRedirect("/roi", "?fuente=codex")).toBe("/gasto/roi?fuente=codex");
    expect(legacyRedirect("/cliente/Mi%20Cliente", "?proyecto=%2Fa")).toBe("/proyectos/Mi%20Cliente?proyecto=%2Fa");
  });
  it("rutas vigentes no redirigen", () => {
    expect(legacyRedirect("/gasto", "")).toBeNull();
    expect(legacyRedirect("/", "")).toBeNull();
  });
});

describe("withSource", () => {
  it("conserva ?fuente= de la URL actual y no pisa uno explícito", () => {
    expect(withSource("/actividad?dia=2026-09-27", "?fuente=codex&dia=2026-01-01")).toBe("/actividad?dia=2026-09-27&fuente=codex");
    expect(withSource("/gasto?fuente=claude-code", "?fuente=codex")).toBe("/gasto?fuente=claude-code");
    expect(withSource("/configuracion", "")).toBe("/configuracion");
  });
});

describe("promptPath", () => {
  it("ruta de la vista estilo shell", () => {
    expect(promptPath("/")).toBe("~");
    expect(promptPath("/gasto/roi")).toBe("~/gasto/roi");
    expect(promptPath("/proyectos/Mi%20Cliente")).toBe("~/proyectos/Mi Cliente");
  });
});

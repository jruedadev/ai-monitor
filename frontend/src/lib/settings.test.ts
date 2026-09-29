import { describe, expect, it } from "vitest";
import type { UsageSnapshot } from "@/lib/api";
import { projectPaths, sourceStatuses } from "@/lib/settings";

const usage = { total_tokens: 1 } as UsageSnapshot["sources"]["claude_code"][string];

describe("sourceStatuses", () => {
  it("sin snapshot → lista vacía", () => {
    expect(sourceStatuses(null)).toEqual([]);
  });

  it("con datos, sin datos y OpenRouter sin clave", () => {
    const sources = {
      claude_code: { "/a": usage, "/b": usage }, codex: {}, opencode: {}, hermes: {},
      openrouter: { unavailable: true, reason: "OPENROUTER_API_KEY no configurada" },
    } as UsageSnapshot["sources"];
    const byKey = Object.fromEntries(sourceStatuses(sources).map((s) => [s.key, s]));
    expect(byKey.claude_code).toMatchObject({ state: "data", detail: "2 proyectos" });
    expect(byKey.codex).toMatchObject({ state: "empty", detail: "Sin datos (no instalado o sin uso)" });
    expect(byKey.openrouter).toMatchObject({ state: "unavailable", detail: "OPENROUTER_API_KEY no configurada" });
  });

  it("OpenRouter disponible cuenta modelos", () => {
    const sources = {
      claude_code: {}, codex: {}, opencode: {}, hermes: {},
      openrouter: { unavailable: false, models: { a: { tokens: 1, cost: 1, requests: 1 } } },
    } as UsageSnapshot["sources"];
    expect(sourceStatuses(sources).find((s) => s.key === "openrouter")).toMatchObject({ state: "data", detail: "1 modelo" });
  });
});

describe("projectPaths", () => {
  it("une los proyectos de las cuatro fuentes por proyecto, sin OpenRouter, ordenados y sin duplicar", () => {
    const sources = {
      claude_code: { "/b": usage, "/a": usage }, codex: { "/a": usage }, opencode: {}, hermes: { "/c": usage },
      openrouter: { unavailable: false, models: { m: { tokens: 1, cost: 1, requests: 1 } } },
    } as UsageSnapshot["sources"];
    expect(projectPaths(sources)).toEqual(["/a", "/b", "/c"]);
    expect(projectPaths(null)).toEqual([]);
  });
});

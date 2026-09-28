import { describe, expect, it } from "vitest";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { buildCommandEntries } from "@/lib/commands";

const combined: Record<string, ProjectUsage> = {
  "/home/u/DEV/ACME/app": { total_tokens: 1, cost: 1, messages: 1, session_count: 1, by_source: ["claude_code"] },
};
const sources = {
  claude_code: {
    "/home/u/DEV/ACME/app": {
      sessions_detail: [
        { session_id: "s1", tokens: 1, cost: 1, title: "Arreglar login", first_ts: null, last_ts: null, cwd: null, date: "2026-09-20" },
        { session_id: "s2", tokens: 1, cost: 1, title: null, first_ts: null, last_ts: null, cwd: null, date: "2026-09-21" },
      ],
    },
  },
  codex: {}, opencode: {}, hermes: {}, openrouter: { unavailable: true },
} as unknown as UsageSnapshot["sources"];

describe("buildCommandEntries", () => {
  const entries = buildCommandEntries(sources, combined);
  const byGroup = (g: string) => entries.filter((e) => e.group === g);

  it("incluye las siete vistas", () => {
    expect(byGroup("Vistas").map((e) => e.to)).toEqual(["/", "/actividad", "/gasto", "/gasto/roi", "/proyectos", "/recomendaciones", "/configuracion"]);
  });
  it("clientes y proyectos enlazan a /proyectos, sin heredar el filtro de fuente", () => {
    expect(byGroup("Clientes")[0]).toMatchObject({ label: "ACME", to: "/proyectos/ACME" });
    expect(byGroup("Proyectos")[0]).toMatchObject({
      label: "app", hint: "/home/u/DEV/ACME/app", to: "/proyectos/ACME?proyecto=%2Fhome%2Fu%2FDEV%2FACME%2Fapp",
      keepSource: false,
    });
  });
  it("solo sesiones con título, enlazadas a su día y a la fuente propia de la sesión", () => {
    expect(byGroup("Sesiones")).toHaveLength(1);
    expect(byGroup("Sesiones")[0]).toMatchObject({
      label: "Arreglar login", to: "/actividad?dia=2026-09-20&fuente=claude-code",
    });
  });
  it("sin snapshot solo quedan las vistas", () => {
    expect(buildCommandEntries(null, null).every((e) => e.group === "Vistas")).toBe(true);
  });
  it("ids únicos", () => {
    expect(new Set(entries.map((e) => e.id)).size).toBe(entries.length);
  });
});

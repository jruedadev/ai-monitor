import { describe, expect, it } from "vitest";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";
import { BASIC_THINKING_MS, OFFICE_WINDOW_MS, deriveOfficeAgents } from "@/lib/office";

const NOW = Date.parse("2026-10-01T12:00:00Z");

function session(id: string, lastMs: number | string): SessionDetailEntry {
  const last_ts = typeof lastMs === "number" ? new Date(lastMs).toISOString() : lastMs;
  return { session_id: id, tokens: 1, cost: 0, title: null, first_ts: null, last_ts, cwd: null, date: null };
}

export function sources(entries: Record<string, Record<string, SessionDetailEntry[]>>): UsageSnapshot["sources"] {
  const out: Record<string, unknown> = {};
  for (const [source, projects] of Object.entries(entries)) {
    out[source] = Object.fromEntries(Object.entries(projects).map(([p, s]) => [p, { sessions_detail: s }]));
  }
  return out as UsageSnapshot["sources"];
}

describe("deriveOfficeAgents", () => {
  it("convierte cada sesión reciente en un agente básico: thinking < 3 min, idle después", () => {
    const agents = deriveOfficeAgents(
      sources({
        claude_code: { "/srv/acme/web": [session("a", NOW - 60_000)] },
        codex: { "/srv/acme/api": [session("b", NOW - BASIC_THINKING_MS - 1)] },
      }),
      NOW,
    );
    expect(agents).toEqual([
      { key: "claude_code:a", source: "claude_code", project: "/srv/acme/web", label: "web", state: "thinking",
        tool: null, toolKind: null, sinceMs: NOW - 60_000, live: false },
      { key: "codex:b", source: "codex", project: "/srv/acme/api", label: "api", state: "idle",
        tool: null, toolKind: null, sinceMs: NOW - BASIC_THINKING_MS - 1, live: false },
    ]);
  });

  it("descarta sesiones fuera de la ventana, sin last_ts o con fecha inválida", () => {
    const stale = session("viejo", NOW - OFFICE_WINDOW_MS - 1);
    const noTs = { ...session("sin", NOW), last_ts: null };
    const broken = session("roto", "no-es-fecha");
    expect(deriveOfficeAgents(sources({ claude_code: { "/p": [stale, noTs, broken] } }), NOW)).toEqual([]);
  });

  it("ignora OpenRouter, ordena por actividad reciente y respeta el límite", () => {
    const agents = deriveOfficeAgents(
      sources({
        claude_code: { "/p/uno": [session("1", NOW - 5_000), session("2", NOW - 1_000), session("3", NOW - 9_000)] },
        openrouter: { "/p/or": [session("x", NOW)] },
      }),
      NOW,
      2,
    );
    expect(agents.map((a) => a.key)).toEqual(["claude_code:2", "claude_code:1"]);
  });

  it("acepta epoch en ms (OpenCode) y descarta marcas en el futuro", () => {
    const opencode = { ...session("oc", NOW), last_ts: NOW - 30_000 };
    const future = session("fut", NOW + 10 * 60_000);
    const agents = deriveOfficeAgents(sources({ opencode: { "/p/oc": [opencode] }, claude_code: { "/p/f": [future] } }), NOW);
    expect(agents.map((a) => [a.key, a.state])).toEqual([["opencode:oc", "thinking"]]);
  });

  it("devuelve [] sin datos", () => {
    expect(deriveOfficeAgents(null, NOW)).toEqual([]);
  });
});

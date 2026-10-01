import { describe, expect, it, vi } from "vitest";
import type { SessionDetailEntry, UsageSnapshot } from "@/lib/api";
import { fetchActivity, mergeOfficeAgents, type ActivityAgent, type ActivitySnapshot } from "@/lib/activity";
import { OFFICE_MAX_AGENTS } from "@/lib/office";

const NOW = Date.parse("2026-10-01T12:00:00Z");
const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");

function sess(id: string, lastMs: number): SessionDetailEntry {
  return { session_id: id, tokens: 1, cost: 0, title: null, first_ts: null, last_ts: new Date(lastMs).toISOString(), cwd: null, date: null };
}
function usage(entries: Record<string, Record<string, SessionDetailEntry[]>>): UsageSnapshot["sources"] {
  const out: Record<string, unknown> = {};
  for (const [s, p] of Object.entries(entries)) {
    out[s] = Object.fromEntries(Object.entries(p).map(([k, v]) => [k, { sessions_detail: v }]));
  }
  return out as UsageSnapshot["sources"];
}
function agent(key: string, over: Partial<ActivityAgent> = {}): ActivityAgent {
  const [source] = key.split(":");
  return { key, source, project: "/srv/acme/web", state: "tool", tool: "Bash", tool_kind: "run", since: iso(NOW - 3_000), ...over };
}
function act(agents: ActivityAgent[], sources: ActivitySnapshot["sources"]): ActivitySnapshot {
  return { generated_at: iso(NOW), agents, sources };
}
const ALL_OK = { claude_code: "ok", opencode: "ok", hermes: "ok" } as const;

describe("mergeOfficeAgents", () => {
  it("sin activity (null) todo viene del estado básico de /api/usage", () => {
    const agents = mergeOfficeAgents(null, usage({ claude_code: { "/p": [sess("a", NOW - 1_000)] } }), NOW);
    expect(agents.map((a) => [a.key, a.live, a.state])).toEqual([["claude_code:a", false, "thinking"]]);
  });

  it("una fuente en vivo 'ok' viene de activity y sus sesiones de usage se descartan", () => {
    const agents = mergeOfficeAgents(
      act([agent("claude_code:a")], ALL_OK),
      usage({ claude_code: { "/p": [sess("a", NOW - 1_000), sess("otra", NOW - 2_000)] } }),
      NOW,
    );
    expect(agents).toEqual([{
      key: "claude_code:a", source: "claude_code", project: "/srv/acme/web", label: "web", state: "tool",
      tool: "Bash", toolKind: "run", sinceMs: NOW - 3_000, live: true,
    }]);
  });

  it("una fuente 'unavailable' cae al estado básico de usage", () => {
    const agents = mergeOfficeAgents(
      act([], { ...ALL_OK, hermes: "unavailable" }),
      usage({ hermes: { "/h": [sess("h1", NOW - 5_000)] } }),
      NOW,
    );
    expect(agents.map((a) => [a.key, a.live])).toEqual([["hermes:h1", false]]);
  });

  it("Codex siempre sale de usage, aunque activity esté 'ok' en todo lo demás", () => {
    const agents = mergeOfficeAgents(act([], ALL_OK), usage({ codex: { "/c": [sess("c1", NOW - 5_000)] } }), NOW);
    expect(agents.map((a) => [a.key, a.live])).toEqual([["codex:c1", false]]);
  });

  it("nunca incluye OpenRouter", () => {
    const agents = mergeOfficeAgents(null, usage({ openrouter: { "/or": [sess("x", NOW)] } }), NOW);
    expect(agents).toEqual([]);
  });

  it("si una key llega de ambos lados gana activity", () => {
    const agents = mergeOfficeAgents(
      act([agent("claude_code:a", { state: "waiting" })], ALL_OK),
      usage({ claude_code: { "/p": [sess("a", NOW - 1_000)] } }),
      NOW,
    );
    expect(agents).toHaveLength(1);
    expect(agents[0].state).toBe("waiting");
    expect(agents[0].live).toBe(true);
  });

  it("ordena por sinceMs descendente y respeta el tope", () => {
    const many = Array.from({ length: OFFICE_MAX_AGENTS + 5 }, (_, i) =>
      agent(`claude_code:s${i}`, { since: iso(NOW - (i + 1) * 1_000) }));
    const agents = mergeOfficeAgents(act(many, ALL_OK), usage({}), NOW);
    expect(agents).toHaveLength(OFFICE_MAX_AGENTS);
    expect(agents[0].key).toBe("claude_code:s0");
    expect(agents.map((a) => a.sinceMs)).toEqual(agents.map((a) => a.sinceMs).sort((a, b) => b - a));
  });

  it("ignora agentes de activity con fecha o fuente inválidas", () => {
    const agents = mergeOfficeAgents(
      act([agent("claude_code:ok"), agent("claude_code:mala", { since: "no-es-fecha" }), agent("codex:x", { source: "codex" })], ALL_OK),
      usage({}),
      NOW,
    );
    expect(agents.map((a) => a.key)).toEqual(["claude_code:ok"]);
  });

  it("un proyecto 'unknown' no rompe la etiqueta", () => {
    const agents = mergeOfficeAgents(act([agent("claude_code:a", { project: "unknown" })], ALL_OK), usage({}), NOW);
    expect(agents[0].label).toBe("unknown");
  });
});

describe("fetchActivity", () => {
  it("devuelve el snapshot si la respuesta es 200", async () => {
    const snap = act([], ALL_OK);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => snap });
    await expect(fetchActivity(fetchImpl as unknown as typeof fetch)).resolves.toEqual(snap);
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/activity");
  });

  it("devuelve null ante error de red, estado no-ok o cuerpo inválido", async () => {
    await expect(fetchActivity(vi.fn().mockRejectedValue(new Error("red")) as unknown as typeof fetch)).resolves.toBeNull();
    await expect(fetchActivity(vi.fn().mockResolvedValue({ ok: false }) as unknown as typeof fetch)).resolves.toBeNull();
    await expect(
      fetchActivity(vi.fn().mockResolvedValue({ ok: true, json: async () => ({ otra: 1 }) }) as unknown as typeof fetch),
    ).resolves.toBeNull();
  });

  it("aborta pasados 5 s", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn((_url: string, init?: RequestInit) =>
      new Promise((_res, rej) => init?.signal?.addEventListener("abort", () => rej(new Error("abort")))));
    const pending = fetchActivity(fetchImpl as unknown as typeof fetch, 5_000);
    await vi.advanceTimersByTimeAsync(5_001);
    await expect(pending).resolves.toBeNull();
    vi.useRealTimers();
  });
});

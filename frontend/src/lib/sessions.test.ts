import { describe, expect, it } from "vitest";
import type { UsageSnapshot } from "@/lib/api";
import { collectSessions, groupSessionsBySource, sessionDurationSeconds, toEpochMs } from "@/lib/sessions";

describe("toEpochMs", () => {
  it("interpreta ISO, segundos y milisegundos", () => {
    expect(toEpochMs("2026-10-01T12:00:00Z")).toBe(Date.parse("2026-10-01T12:00:00Z"));
    expect(toEpochMs(1_790_000_000)).toBe(1_790_000_000_000);
    expect(toEpochMs(1_790_000_000_000)).toBe(1_790_000_000_000);
  });
  it("devuelve null para null e inválidos", () => {
    expect(toEpochMs(null)).toBeNull();
    expect(toEpochMs("no-es-fecha")).toBeNull();
    expect(toEpochMs(Number.NaN)).toBeNull();
  });
});

describe("sessionDurationSeconds", () => {
  it("calcula bien una sesión de OpenCode (ms)", () => {
    expect(sessionDurationSeconds({ first_ts: 1_790_000_000_000, last_ts: 1_790_000_090_000 })).toBe(90);
  });
  it("mantiene segundos (Codex) e ISO (Claude Code)", () => {
    expect(sessionDurationSeconds({ first_ts: 1_790_000_000, last_ts: 1_790_000_060 })).toBe(60);
    expect(sessionDurationSeconds({ first_ts: "2026-10-01T12:00:00Z", last_ts: "2026-10-01T12:01:00Z" })).toBe(60);
  });
});

describe("collectSessions con varias cuentas", () => {
  const mk = (id: string) => ({ total_tokens: 1, cost: 1, messages: 1, session_count: 1, by_day: {},
    sessions_detail: [{ session_id: id, tokens: 1, cost: 1, title: null, first_ts: null, last_ts: null, cwd: null, date: null }] });
  const sources = {
    claude_code: { "/p/a": mk("s-def") }, "claude_code@robc": { "/p/b": mk("s-robc") },
    codex: {}, opencode: {}, hermes: {}, openrouter: { unavailable: true },
  } as unknown as UsageSnapshot["sources"];
  const ids = (section: Parameters<typeof collectSessions>[1]) => collectSessions(sources, section).map((s) => s.session_id).sort();

  it("una cuenta da solo sus sesiones", () => expect(ids("claude_code@robc")).toEqual(["s-robc"]));
  it("claude_code suma todas las cuentas", () => expect(ids("claude_code")).toEqual(["s-def", "s-robc"]));
  it("all incluye las cuentas de Claude", () => expect(ids("all")).toEqual(["s-def", "s-robc"]));
});

describe("groupSessionsBySource", () => {
  it("agrupa por fuente, incluidas las claves de cuenta", () => {
    const row = (source: string) => ({ source, project: "/p", session_id: source, tokens: 1, cost: 1, title: null, first_ts: null, last_ts: null, cwd: null, date: null });
    const groups = groupSessionsBySource([row("claude_code@robc"), row("codex"), row("claude_code")]);
    expect(groups.map((g) => g.source)).toEqual(["claude_code", "codex", "claude_code@robc"]);
  });
});

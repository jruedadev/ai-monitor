import { describe, expect, it } from "vitest";
import { sessionDurationSeconds, toEpochMs } from "@/lib/sessions";

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

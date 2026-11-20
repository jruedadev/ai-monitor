import { describe, expect, it } from "vitest";
import type { ProjectUsage, UsageSnapshot } from "@/lib/api";
import { DEFAULT_CLIENT_ROOTS } from "@/lib/clients";
import { projectsFor } from "@/lib/projects";

const usage = (cost: number) => ({ total_tokens: 10, cost, messages: 1, session_count: 1 }) as UsageSnapshot["sources"]["codex"][string];
const combined: Record<string, ProjectUsage> = {
  "/home/u/DEV/A/x": { total_tokens: 20, cost: 3, messages: 2, session_count: 2, by_source: ["claude_code", "codex"] },
  "/home/u/DEV/B/y": { total_tokens: 5, cost: 1, messages: 1, session_count: 1, by_source: ["claude_code"] },
};
const sources = {
  claude_code: {}, codex: { "/home/u/DEV/A/x": usage(2) }, opencode: {}, hermes: {},
  openrouter: { unavailable: false, models: { "m-1": { tokens: 7, cost: 4, requests: 3 } } },
} as UsageSnapshot["sources"];

const twoAccounts = {
  claude_code: { "/p/a": usage(5), "/p/shared": usage(1) },
  "claude_code@robc": { "/p/b": usage(7), "/p/shared": usage(2) },
  codex: {}, opencode: {}, hermes: {}, openrouter: { unavailable: true },
} as unknown as UsageSnapshot["sources"];

describe("projectsFor con varias cuentas", () => {
  it("una cuenta da solo sus proyectos", () => {
    const r = projectsFor(twoAccounts, combined, "claude_code@robc", null, DEFAULT_CLIENT_ROOTS);
    expect(Object.keys(r).sort()).toEqual(["/p/b", "/p/shared"]);
    expect(r["/p/shared"].cost).toBe(2);
    expect(r["/p/b"].by_source).toEqual(["claude_code@robc"]);
  });
  it("claude_code suma todas las cuentas", () => {
    const r = projectsFor(twoAccounts, combined, "claude_code", null, DEFAULT_CLIENT_ROOTS);
    expect(Object.keys(r).sort()).toEqual(["/p/a", "/p/b", "/p/shared"]);
    expect(r["/p/shared"].cost).toBe(3);
    expect(r["/p/shared"].total_tokens).toBe(20);
  });
});

describe("projectsFor", () => {
  it("all usa la vista combinada y filtra por cliente", () => {
    expect(Object.keys(projectsFor(sources, combined, "all", null, DEFAULT_CLIENT_ROOTS))).toHaveLength(2);
    expect(Object.keys(projectsFor(sources, combined, "all", "B", DEFAULT_CLIENT_ROOTS))).toEqual(["/home/u/DEV/B/y"]);
  });
  it("una fuente usa sus propios proyectos", () => {
    expect(projectsFor(sources, combined, "codex", null, DEFAULT_CLIENT_ROOTS)["/home/u/DEV/A/x"]).toMatchObject({ cost: 2, by_source: ["codex"] });
  });
  it("OpenRouter agrupa por modelo y sin datos devuelve vacío", () => {
    expect(projectsFor(sources, combined, "openrouter", null, DEFAULT_CLIENT_ROOTS)["m-1"]).toMatchObject({ total_tokens: 7, cost: 4, messages: 3 });
    expect(projectsFor(null, null, "all", null, DEFAULT_CLIENT_ROOTS)).toEqual({});
  });

  it("filtra por cliente con raíces propias", () => {
    const roots = [{ root: "/home/u/DEV/A", mode: "plano" as const }];
    expect(Object.keys(projectsFor(sources, combined, "all", "A", roots))).toEqual(["/home/u/DEV/A/x"]);
  });
});

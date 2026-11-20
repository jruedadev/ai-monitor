import { describe, expect, it } from "vitest";
import { accountSourceLabel, normalizeFuente } from "@/lib/sources";
import { parseSource, sourceSlug } from "@/lib/routes";

describe("fuente de una cuenta", () => {
  it("normalizeFuente acepta la forma con guion del enlace del briefing", () => {
    expect(normalizeFuente("claude-code@trabajo")).toBe("claude_code@trabajo");
    expect(normalizeFuente("claude_code@trabajo")).toBe("claude_code@trabajo");
    expect(normalizeFuente("claude-code")).toBe("claude-code");
  });

  it("parseSource resuelve ?fuente=claude-code@<id> a claude_code@<id>", () => {
    expect(parseSource("claude-code@trabajo")).toBe("claude_code@trabajo");
    expect(parseSource("claude-code@")).toBe("all");
  });

  it("la URL usa la forma con guion; la API, la de guion bajo", () => {
    expect(sourceSlug("claude_code@trabajo")).toBe("claude-code@trabajo");
  });

  it("accountSourceLabel", () => {
    expect(accountSourceLabel("Trabajo")).toBe("Trabajo (Claude Code)");
  });
});

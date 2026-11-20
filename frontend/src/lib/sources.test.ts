import { describe, expect, it } from "vitest";
import { accountSourceLabel, normalizeFuente, sourceChipLabel, sourceMeta } from "@/lib/sources";
import { parseSource, sourceSlug } from "@/lib/routes";
import type { Account } from "@/lib/api";

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

describe("parseSource con cuentas configuradas", () => {
  const accounts = [{ id: "robc" }] as Account[];
  it("acepta una cuenta existente y cae a all si el id no existe", () => {
    expect(parseSource("claude-code@robc", accounts)).toBe("claude_code@robc");
    expect(parseSource("claude-code@viejo", accounts)).toBe("all");
    expect(parseSource("codex", accounts)).toBe("codex");
  });
});

describe("identidad de una fuente de cuenta", () => {
  it("sourceMeta y la etiqueta del chip no fallan con claves de cuenta", () => {
    expect(sourceMeta("claude_code@robc").label).toBe("Claude Code");
    expect(sourceChipLabel("claude_code@robc")).toBe("Claude Code (robc)");
    expect(sourceChipLabel("codex")).toBe("Codex");
    expect(sourceChipLabel("raro")).toBe("raro");
  });
});

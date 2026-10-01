import { describe, expect, it } from "vitest";
import type { OfficeAgent } from "@/lib/office";
import { statusText } from "@/views/OfficeView";

const NOW = 1_000_000;
const base: OfficeAgent = {
  key: "claude_code:a", source: "claude_code", project: "/p", label: "p", state: "tool",
  tool: "Bash", toolKind: "run", sinceMs: NOW, live: true,
};

describe("statusText", () => {
  it("describe cada estado en español", () => {
    expect(statusText(base, NOW)).toBe("ejecutando Bash");
    expect(statusText({ ...base, toolKind: "edit" }, NOW)).toBe("editando");
    expect(statusText({ ...base, toolKind: "read" }, NOW)).toBe("leyendo");
    expect(statusText({ ...base, toolKind: "other", tool: "mcp__x" }, NOW)).toBe("usando mcp__x");
    expect(statusText({ ...base, state: "waiting", sinceMs: NOW - 12_400 }, NOW)).toBe("esperando · 12 s");
    expect(statusText({ ...base, state: "thinking", tool: null, toolKind: null }, NOW)).toBe("pensando");
    expect(statusText({ ...base, state: "idle", tool: null, toolKind: null }, NOW)).toBe("en pausa");
  });
});

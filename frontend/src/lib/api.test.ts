import { afterEach, describe, expect, it, vi } from "vitest";
import { HttpError, fetchBriefing } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchBriefing", () => {
  it("arma la query con source y compare", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await fetchBriefing("claude_code", "2026-08");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/briefing?source=claude_code&compare=2026-08");
  });

  it("un 400 llega como HttpError con status y el mensaje del backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "No hay datos para comparar con 1999-01" }), { status: 400 }),
    ));
    const err = await fetchBriefing("all", "1999-01").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(HttpError);
    expect((err as HttpError).status).toBe(400);
    expect((err as HttpError).message).toContain("No hay datos para comparar con 1999-01");
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { HttpError, fetchBriefing, runRecommendations, setRecommendationStatus } from "@/lib/api";

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

describe("API del motor de recomendaciones", () => {
  it("runRecommendations manda JSON (defensa CSRF) y un 409 llega como HttpError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Ya hay una corrida en curso" }), { status: 409 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const err = await runRecommendations().catch((e: unknown) => e);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/recommendations/run");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    expect((err as HttpError).status).toBe(409);
  });

  it("setRecommendationStatus codifica el id y envía el estado", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await setRecommendationStatus("abc123", "aplicada");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/recommendations/abc123/estado");
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ status: "aplicada" }));
  });
});

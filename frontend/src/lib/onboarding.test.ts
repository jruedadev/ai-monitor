import { describe, expect, it, vi } from "vitest";
import { HttpError } from "@/lib/api";
import {
  saveOnboarding, shouldRedirectToOnboarding, skipDraft, suggestBackend, suggestRoots, type OnboardingDraft,
} from "@/lib/onboarding";

const ready = { loading: false, error: null, degraded: false, completedAt: null };

describe("shouldRedirectToOnboarding", () => {
  it("redirige solo con ajustes cargados, sin error y sin completar", () => {
    expect(shouldRedirectToOnboarding(ready, "/")).toBe(true);
    expect(shouldRedirectToOnboarding(ready, "/gasto/roi")).toBe(true);
    expect(shouldRedirectToOnboarding(ready, "/bienvenida")).toBe(false);
    expect(shouldRedirectToOnboarding({ ...ready, completedAt: "2026-09-29T10:00:00+00:00" }, "/")).toBe(false);
  });
  it("nunca atrapa al usuario si no se pudo leer el estado", () => {
    expect(shouldRedirectToOnboarding({ ...ready, loading: true }, "/")).toBe(false);
    expect(shouldRedirectToOnboarding({ ...ready, error: "HTTP 404" }, "/")).toBe(false);
    expect(shouldRedirectToOnboarding({ ...ready, degraded: true }, "/")).toBe(false);
  });
});

describe("suggestRoots", () => {
  it("propone la carpeta común dos niveles arriba, sin duplicar por mayúsculas", () => {
    expect(suggestRoots(["/home/u/DEV/ACME/app", "/home/u/DEV/BETA/api", "/home/u/dev/GAMMA/x"])).toEqual([
      { root: "DEV", mode: "cliente" },
    ]);
  });
  it("ordena por frecuencia y limita a tres", () => {
    const paths = ["/srv/work/A/x", "/srv/work/B/y", "/srv/work/C/z", "/opt/src/D/q", "/opt/src/E/r"];
    expect(suggestRoots(paths)).toEqual([{ root: "work", mode: "cliente" }, { root: "src", mode: "cliente" }]);
  });
  it("descarta home, Users y el nombre de usuario", () => {
    expect(suggestRoots(["/home/u/app", "/home/u/api", "/Users/ana/code/x", "/Users/ana/code/y"])).toEqual([
      { root: "DEV", mode: "cliente" },
    ]);
  });
  it("sin proyectos o con uno solo por carpeta → valor por defecto", () => {
    expect(suggestRoots([])).toEqual([{ root: "DEV", mode: "cliente" }]);
    expect(suggestRoots(["/srv/work/A/x"])).toEqual([{ root: "DEV", mode: "cliente" }]);
  });
});

describe("suggestBackend", () => {
  it("hermes → claude → none", () => {
    expect(suggestBackend({ hermes: true, claude: true })).toBe("hermes");
    expect(suggestBackend({ hermes: false, claude: true })).toBe("claude");
    expect(suggestBackend({ hermes: false, claude: false })).toBe("none");
  });
});

describe("saveOnboarding", () => {
  const draft: OnboardingDraft = {
    roots: [{ root: "DEV", mode: "cliente" }],
    roi: { hourly_rate: 30 },
    engine: { backend: "none", llm_chain: ["nous:x:free"] },
  };
  const fakeApi = () => ({
    saveAppSettings: vi.fn().mockResolvedValue({}),
    saveRoiSettings: vi.fn().mockResolvedValue({}),
    saveEngineSettings: vi.fn().mockResolvedValue({}),
    completeOnboarding: vi.fn().mockResolvedValue({ onboarding_completed_at: "t" }),
  });

  it("guarda en orden y marca el onboarding al final", async () => {
    const api = fakeApi();
    const calls: string[] = [];
    for (const [name, fn] of Object.entries(api)) fn.mockImplementation(async () => { calls.push(name); return {}; });
    expect(await saveOnboarding(draft, api)).toEqual({ ok: true });
    expect(calls).toEqual(["saveAppSettings", "saveRoiSettings", "saveEngineSettings", "completeOnboarding"]);
    expect(api.saveAppSettings).toHaveBeenCalledWith({ client_roots: draft.roots });
  });

  it("roi null no toca ROI", async () => {
    const api = fakeApi();
    await saveOnboarding({ ...draft, roi: null }, api);
    expect(api.saveRoiSettings).not.toHaveBeenCalled();
  });

  it("un fallo detiene el guardado, no marca el onboarding e indica el paso", async () => {
    const api = fakeApi();
    api.saveRoiSettings.mockRejectedValue(new HttpError("POST /api/roi-settings → HTTP 400: hourly_rate debe ser numérico o null", 400));
    expect(await saveOnboarding(draft, api)).toEqual({ ok: false, step: "roi", message: "hourly_rate debe ser numérico o null" });
    expect(api.saveEngineSettings).not.toHaveBeenCalled();
    expect(api.completeOnboarding).not.toHaveBeenCalled();
  });

  it("un error de red usa un mensaje genérico", async () => {
    const api = fakeApi();
    api.completeOnboarding.mockRejectedValue(new TypeError("Failed to fetch"));
    expect(await saveOnboarding(draft, api)).toEqual({
      ok: false, step: "engine", message: "No se pudo guardar. Revisa que el servidor siga activo e inténtalo de nuevo.",
    });
  });
});

describe("skipDraft", () => {
  it("raíces por defecto, backend sugerido, sin ROI", () => {
    expect(skipDraft({ hermes: false, claude: true }, ["a:b:free"])).toEqual({
      roots: [{ root: "DEV", mode: "cliente" }], roi: null, engine: { backend: "claude", llm_chain: ["a:b:free"] },
    });
  });
});

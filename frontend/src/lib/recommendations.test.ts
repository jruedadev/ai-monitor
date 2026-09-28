// frontend/src/lib/recommendations.test.ts
import { describe, expect, it } from "vitest";
import { HttpError, type PatternEvidence, type Recommendation, type RecommendationRun, type RecommendationsResponse } from "@/lib/api";
import {
  emptyMessage, evidenceLines, filterBySource, isRunInProgress, parseChain, parseRecTab, recommendationsLine,
  removeRecommendation, restoreRecommendation, runErrorMessage, runModelLabel,
} from "@/lib/recommendations";

const norm = (lines: string[]) => lines.map((l) => l.replace(/\s/g, " "));

const EV: PatternEvidence = {
  sessions: 4, days: 3, tokens: 1200, projects: ["/home/u/DEV/ACME/app"], sources: ["claude_code"], snippets: ["revisa los logs"],
};

function rec(id: string, extra: Partial<Recommendation> = {}): Recommendation {
  return {
    id, first_seen: "2026-09-20T07:00:00+00:00", last_seen: "2026-09-21T07:00:00+00:00", tool: "claude_code",
    tokens: 1200, pattern: `patrón ${id}`, kind: "skill", description: "d", impact: "medio",
    evidence: EV,
    draft: "---\nname: x\n---", status: "nueva", status_at: null, generator: "reglas", ...extra,
  };
}

const RUN: RecommendationRun = {
  id: 3, started_at: "2026-09-21T12:00:00+00:00", finished_at: "2026-09-21T12:01:00+00:00", trigger: "diario",
  backend: "hermes", model: "nous:upstage/solar-pro4:free", attempts: 1, status: "ok", prompts: 80, clusters: 2,
  created: 1, updated: 1, resolved: 0, error: null, llm_tokens: 900, llm_cost: 0,
};

describe("parseRecTab", () => {
  it("acepta las cuatro pestañas y cae en nueva", () => {
    expect(parseRecTab("aplicada")).toBe("aplicada");
    expect(parseRecTab("resuelta")).toBe("resuelta");
    expect(parseRecTab("todas")).toBe("nueva");
    expect(parseRecTab(null)).toBe("nueva");
  });
});

describe("filterBySource", () => {
  const multi = rec("m", { tool: "varias", evidence: { ...EV, sources: ["codex", "hermes"] } });
  const list = [rec("a"), rec("b", { tool: "codex", evidence: { ...EV, sources: ["codex"] } }), multi];
  it("sin filtro devuelve todo", () => expect(filterBySource(list, "all")).toHaveLength(3));
  it("filtra por tool y por las fuentes de un patrón compartido", () => {
    expect(filterBySource(list, "codex").map((r) => r.id)).toEqual(["b", "m"]);
    expect(filterBySource(list, "claude_code").map((r) => r.id)).toEqual(["a"]);
    expect(filterBySource(list, "openrouter")).toEqual([]);
  });
});

describe("evidenceLines", () => {
  it("resume un patrón en texto plano", () => {
    expect(norm(evidenceLines(rec("a")))).toEqual(["4 sesiones en 3 días", "1,2 K tokens", "Proyectos: app"]);
  });
  it("singular y sin proyectos", () => {
    const r = rec("a", { evidence: { sessions: 1, days: 1, tokens: 5, projects: [], sources: [], snippets: [] } });
    expect(norm(evidenceLines(r))).toEqual(["1 sesión en 1 día", "5 tokens"]);
  });
  it("una recomendación de costo muestra los ítems de la señal", () => {
    const r = rec("c", { kind: "costo", evidence: { rule: "spike_day", items: ["Día 20: 3× la mediana"], link: "/actividad?dia=2026-09-20", projects: [], sources: ["claude_code"] } });
    expect(evidenceLines(r)).toEqual(["Día 20: 3× la mediana"]);
  });
});

describe("acciones optimistas", () => {
  it("quitar y restaurar deja la lista igual, en la misma posición", () => {
    const list = [rec("a"), rec("b"), rec("c")];
    const { next, removed } = removeRecommendation(list, "b");
    expect(next.map((r) => r.id)).toEqual(["a", "c"]);
    expect(restoreRecommendation(next, removed).map((r) => r.id)).toEqual(["a", "b", "c"]);
  });
  it("restaurar no duplica si la recomendación ya volvió (p. ej. por una recarga)", () => {
    const list = [rec("a"), rec("b")];
    const { removed } = removeRecommendation(list, "b");
    expect(restoreRecommendation(list, removed).map((r) => r.id)).toEqual(["a", "b"]);
  });
  it("un id desconocido no cambia nada", () => {
    const { next, removed } = removeRecommendation([rec("a")], "zz");
    expect(next.map((r) => r.id)).toEqual(["a"]);
    expect(removed).toBeNull();
  });
});

describe("mensajes", () => {
  it("409 → corrida en curso; otro error → mensaje genérico", () => {
    expect(runErrorMessage(new HttpError("x", 409))).toBe("Ya hay una corrida en curso");
    expect(runErrorMessage(new Error("red caída"))).toBe("No se pudo iniciar el análisis (red caída)");
  });
  it("estados vacíos", () => {
    expect(emptyMessage("nueva", null)).toBe("Aún no hay corridas: pulsa Analizar ahora");
    expect(emptyMessage("nueva", RUN)).toBe("Sin patrones repetidos en los últimos 30 días");
    expect(emptyMessage("aplicada", RUN)).toBe("No has aplicado ninguna recomendación");
    expect(emptyMessage("saltada", RUN)).toBe("No has saltado ninguna recomendación");
    expect(emptyMessage("resuelta", RUN)).toBe("Ninguna recomendación se ha resuelto todavía");
  });
  it("modelo de la corrida", () => {
    expect(runModelLabel(RUN)).toBe("nous:upstage/solar-pro4:free");
    expect(runModelLabel({ ...RUN, model: null, status: "degraded" })).toBe("reglas locales");
    expect(runModelLabel({ ...RUN, backend: "claude", model: "claude" })).toBe("claude -p");
  });
  it("línea del Inicio", () => {
    expect(recommendationsLine(1)).toBe("1 recomendación nueva →");
    expect(recommendationsLine(4)).toBe("4 recomendaciones nuevas →");
  });
});

describe("isRunInProgress", () => {
  const data = (extra: Partial<RecommendationsResponse>): RecommendationsResponse =>
    ({ recommendations: [], last_run: RUN, running: false, degraded: false, ...extra });
  it("el servidor manda", () => expect(isRunInProgress(data({ running: true }), null)).toBe(true));
  it("una corrida pedida sigue en curso hasta verla terminada", () => {
    expect(isRunInProgress(data({ last_run: { ...RUN, id: 2 } }), 3)).toBe(true);
    expect(isRunInProgress(data({ last_run: { ...RUN, finished_at: null, status: "corriendo" } }), 3)).toBe(true);
    expect(isRunInProgress(data({}), 3)).toBe(false);
  });
  it("sin datos ni corrida pedida no hay nada en curso", () => expect(isRunInProgress(null, null)).toBe(false));
});

describe("parseChain", () => {
  it("una entrada por línea, sin vacías ni espacios", () => {
    expect(parseChain(" nous:a:free \n\n nous:b:free\n")).toEqual(["nous:a:free", "nous:b:free"]);
  });
});
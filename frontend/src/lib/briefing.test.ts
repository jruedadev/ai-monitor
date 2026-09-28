import { describe, expect, it } from "vitest";
import type { BriefingResponse, HistoryResponse } from "@/lib/api";
import {
  coverageLabel, dailyCostSeries, formatDeltaPct, isEmptyBriefing, subscriptionHeadline, subscriptionLine, windowLabel,
} from "@/lib/briefing";

function briefing(overrides: Partial<BriefingResponse> = {}): BriefingResponse {
  return {
    source: "all",
    window: { month: "2026-09", from: "2026-09-01", to: "2026-09-27" },
    compare: { month: "2026-08", from: "2026-08-01", to: "2026-08-27", coverage: "full", since: null },
    eligible_months: [{ month: "2026-08", coverage: "full", since: null }],
    kpis: {
      cost: { current: 10, previous: 20, delta_pct: -50 },
      tokens: { current: 100, previous: 50, delta_pct: 100 },
      active_days: { current: 3, previous: 2 },
      cost_incomplete: false,
    },
    subscription: { configured: false, paid: null, api_equivalent: null, winner: null, savings: null },
    top_projects: [],
    attention: [],
    degraded: false,
    ...overrides,
  };
}

describe("formatDeltaPct", () => {
  it("signo explícito, coma decimal y guion para null", () => {
    expect(formatDeltaPct(12.34)).toBe("+12,3 %");
    expect(formatDeltaPct(-17.8)).toBe("−17,8 %");
    expect(formatDeltaPct(0)).toBe("0,0 %");
    expect(formatDeltaPct(null)).toBe("—");
  });
});

describe("etiquetas de ventana y cobertura", () => {
  it("ventana comparada", () => {
    expect(windowLabel(briefing())).toBe("1–27 sept · comparado con 1–27 ago");
  });
  it("sin mes comparable", () => {
    const b = briefing({ compare: { month: "2026-08", from: "2026-08-01", to: "2026-08-27", coverage: "none", since: null } });
    expect(windowLabel(b)).toBe("1–27 sept · sin mes con datos para comparar");
  });
  it("cobertura parcial", () => {
    expect(coverageLabel("2026-07-18")).toBe("cobertura parcial desde 18 jul");
  });
});

describe("suscripción", () => {
  const base = { configured: true, paid: 20, api_equivalent: 657.1 } as const;
  it("gana la suscripción", () => {
    const s = { ...base, winner: "subscription", savings: 637.1 } as const;
    expect(subscriptionLine(s)).toBe("Pagas $ 20,00 · equivale a $ 657,10 · ahorras $ 637,10");
    expect(subscriptionHeadline(s)).toBe("Ahorras $ 637,10");
  });
  it("gana la API", () => {
    const s = { ...base, api_equivalent: 5, winner: "api", savings: 15 } as const;
    expect(subscriptionLine(s)).toBe("Pagas $ 20,00 · equivale a $ 5,00 · la API saldría $ 15,00 más barata");
    expect(subscriptionHeadline(s)).toBe("API más barata por $ 15,00");
  });
  it("empate y sin plan", () => {
    expect(subscriptionHeadline({ ...base, winner: "tie", savings: 0 })).toBe("Empate");
    const none = { configured: false, paid: null, api_equivalent: null, winner: null, savings: null };
    expect(subscriptionLine(none)).toBeNull();
    expect(subscriptionHeadline(none)).toBe("Sin plan configurado");
  });
});

describe("isEmptyBriefing", () => {
  it("vacío solo sin meses elegibles ni actividad", () => {
    const empty = briefing({ eligible_months: [], kpis: { ...briefing().kpis, active_days: { current: 0, previous: null } } });
    expect(isEmptyBriefing(empty)).toBe(true);
    expect(isEmptyBriefing(briefing())).toBe(false);
  });
});

describe("dailyCostSeries", () => {
  const data: HistoryResponse = {
    daily_project: [
      { date: "2026-09-01", source: "claude_code", project: "/p", tokens: 1, cost: 2 },
      { date: "2026-09-01", source: "codex", project: "/p", tokens: 1, cost: 3 },
      { date: "2026-09-03", source: "claude_code", project: "/q", tokens: 1, cost: null },
      { date: "2026-08-31", source: "claude_code", project: "/p", tokens: 1, cost: 9 },
    ],
    daily_model: [{ date: "2026-09-02", model: "__all__", tokens: 1, cost: 7 }],
  };
  it("rellena días sin datos con 0 y suma todas las fuentes de proyecto", () => {
    expect(dailyCostSeries(data, "all", "2026-09-01", "2026-09-03")).toEqual([
      { date: "2026-09-01", cost: 5 }, { date: "2026-09-02", cost: 0 }, { date: "2026-09-03", cost: 0 },
    ]);
  });
  it("filtra por fuente y usa daily_model para OpenRouter", () => {
    expect(dailyCostSeries(data, "codex", "2026-09-01", "2026-09-01")).toEqual([{ date: "2026-09-01", cost: 3 }]);
    expect(dailyCostSeries(data, "openrouter", "2026-09-02", "2026-09-02")).toEqual([{ date: "2026-09-02", cost: 7 }]);
  });
});

import { describe, expect, it } from "vitest";
import { compareCosts, computeSourceRoi, monthRange } from "@/lib/roi";

describe("compareCosts", () => {
  it("la suscripción conviene cuando el costo API equivalente es mayor", () => {
    expect(compareCosts(150, 20)).toEqual({ winner: "subscription", savings: 130 });
  });

  it("la API conviene cuando pagar por uso sale más barato que la suscripción", () => {
    expect(compareCosts(5, 20)).toEqual({ winner: "api", savings: 15 });
  });

  it("empate cuando ambos cuestan lo mismo", () => {
    expect(compareCosts(20, 20)).toEqual({ winner: "tie", savings: 0 });
  });
});

describe("monthRange", () => {
  it("incluye el mes de inicio y el mes actual", () => {
    expect(monthRange("2026-04-07", new Date(2026, 6, 1))).toEqual(["2026-04", "2026-05", "2026-06", "2026-07"]);
  });

  it("cruza el cambio de año", () => {
    expect(monthRange("2025-11-30", new Date(2026, 0, 15))).toEqual(["2025-11", "2025-12", "2026-01"]);
  });

  it("devuelve vacío si el inicio es posterior a hoy", () => {
    expect(monthRange("2026-10-01", new Date(2026, 8, 26))).toEqual([]);
  });
});

const NOW = new Date(2026, 5, 15); // 15 jun 2026
const everything = () => true;

const session = (project: string, date: string, hours: number) => ({
  project,
  date,
  first_ts: `${date}T10:00:00Z`,
  last_ts: new Date(Date.parse(`${date}T10:00:00Z`) + hours * 3_600_000).toISOString(),
});

describe("computeSourceRoi", () => {
  it("sin fecha de inicio usa el costo del snapshot y todas las sesiones", () => {
    const roi = computeSourceRoi({
      source: "claude_code",
      projectCosts: { "/a": 30, "/b": 10 },
      sessions: [session("/a", "2026-01-10", 2), session("/b", "2026-06-01", 3)],
      historyRows: [],
      subscriptionCost: 20,
      subscriptionStart: null,
      hourlyRate: 10,
      matchesScope: everything,
      now: NOW,
    });
    expect(roi.apiCost).toBe(40);
    expect(roi.subscriptionTotal).toBe(20);
    expect(roi.comparison).toEqual({ winner: "subscription", savings: 20 });
    expect(roi.hours).toBeCloseTo(5);
    expect(roi.valueGenerated).toBeCloseTo(50);
    expect(roi.roi).toBeCloseTo(50 / 40);
    expect(roi.monthly).toEqual([]);
  });

  it("con fecha de inicio acota costo, suscripción, horas y ROI a la misma ventana", () => {
    const roi = computeSourceRoi({
      source: "claude_code",
      projectCosts: { "/a": 999 }, // ignorado: con inicio manda el historial
      sessions: [session("/a", "2026-03-31", 10), session("/a", "2026-04-02", 4)],
      historyRows: [
        { date: "2026-03-31", source: "claude_code", project: "/a", tokens: 1, cost: 500 },
        { date: "2026-04-02", source: "claude_code", project: "/a", tokens: 1, cost: 5 },
        { date: "2026-05-10", source: "claude_code", project: "/a", tokens: 1, cost: 60 },
        { date: "2026-05-11", source: "codex", project: "/a", tokens: 1, cost: 1000 },
        { date: "2026-06-01", source: "claude_code", project: "/a", tokens: 1, cost: null },
      ],
      subscriptionCost: 20,
      subscriptionStart: "2026-04-01",
      hourlyRate: 10,
      matchesScope: everything,
      now: NOW,
    });
    expect(roi.months).toBe(3);
    expect(roi.apiCost).toBe(65);
    expect(roi.subscriptionTotal).toBe(60);
    expect(roi.comparison).toEqual({ winner: "subscription", savings: 5 });
    expect(roi.hours).toBeCloseTo(4);
    expect(roi.roi).toBeCloseTo(40 / 65);
    expect(roi.monthly.map((m) => [m.key, m.apiCost, m.comparison?.winner])).toEqual([
      ["2026-04", 5, "api"],
      ["2026-05", 60, "subscription"],
      ["2026-06", 0, "api"],
    ]);
  });

  it("excluye los días del mes de inicio anteriores a la fecha de inicio", () => {
    const roi = computeSourceRoi({
      source: "claude_code",
      projectCosts: {},
      sessions: [],
      historyRows: [
        { date: "2026-04-01", source: "claude_code", project: "/a", tokens: 1, cost: 100 },
        { date: "2026-04-07", source: "claude_code", project: "/a", tokens: 1, cost: 7 },
      ],
      subscriptionCost: 20,
      subscriptionStart: "2026-04-07",
      hourlyRate: null,
      matchesScope: everything,
      now: new Date(2026, 3, 30),
    });
    expect(roi.apiCost).toBe(7);
    expect(roi.comparison).toEqual({ winner: "api", savings: 13 });
  });

  it("respeta el alcance (cliente/proyecto)", () => {
    const roi = computeSourceRoi({
      source: "codex",
      projectCosts: { "/a": 30, "/b": 10 },
      sessions: [session("/a", "2026-01-10", 2), session("/b", "2026-01-10", 3)],
      historyRows: [],
      subscriptionCost: null,
      subscriptionStart: null,
      hourlyRate: null,
      matchesScope: (path) => path === "/b",
      now: NOW,
    });
    expect(roi.apiCost).toBe(10);
    expect(roi.hours).toBeCloseTo(3);
    expect(roi.subscriptionTotal).toBeNull();
    expect(roi.comparison).toBeNull();
    expect(roi.valueGenerated).toBeNull();
    expect(roi.roi).toBeNull();
  });

  it("ROI es null si no hubo costo API", () => {
    const roi = computeSourceRoi({
      source: "codex",
      projectCosts: {},
      sessions: [],
      historyRows: [],
      subscriptionCost: null,
      subscriptionStart: null,
      hourlyRate: 40,
      matchesScope: everything,
      now: NOW,
    });
    expect(roi.valueGenerated).toBe(0);
    expect(roi.roi).toBeNull();
  });
});

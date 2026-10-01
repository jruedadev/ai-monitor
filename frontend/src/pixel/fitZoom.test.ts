import { describe, expect, it } from "vitest";
import { fitZoom } from "@/pixel/fitZoom";

describe("fitZoom", () => {
  it("en escritorio elige el mayor entero que cabe (> 2)", () => {
    // 20x12 baldosas de 16 px: a z=5 → 1600x960 ≤ 1700x1000
    expect(fitZoom(1700, 1000, 20, 12, 1)).toBe(5);
  });
  it("tiene en cuenta el devicePixelRatio", () => {
    expect(fitZoom(850, 500, 20, 12, 2)).toBe(5);
  });
  it("en móvil de 390 px devuelve 2", () => {
    expect(fitZoom(390, 360, 20, 12, 1)).toBe(2);
  });
  it("contenedor diminuto o cero devuelve 2", () => {
    expect(fitZoom(10, 10, 20, 12, 1)).toBe(2);
    expect(fitZoom(0, 0, 20, 12, 1)).toBe(2);
  });
  it("lo limita el eje más estrecho", () => {
    expect(fitZoom(4000, 200, 20, 12, 1)).toBe(2);
  });
});

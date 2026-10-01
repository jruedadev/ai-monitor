import { describe, expect, it } from "vitest";
import { trimLayout } from "./trimLayout";
import type { OfficeLayout } from "./office/types";

const V = 255; // TileType.VOID

function layout(rows: number[][], furniture: OfficeLayout["furniture"] = []): OfficeLayout {
  const tiles = rows.flat() as OfficeLayout["tiles"];
  return {
    version: 1,
    cols: rows[0].length,
    rows: rows.length,
    tiles,
    tileColors: tiles.map((_, i) => (i % 2 ? null : { h: i, s: 0, b: 0, c: 0 })) as OfficeLayout["tileColors"],
    furniture,
  };
}

describe("trimLayout", () => {
  it("recorta filas y columnas vacías dejando una fila de margen arriba para las paredes", () => {
    const out = trimLayout(
      layout([
        [V, V, V, V],
        [V, V, V, V],
        [V, V, V, V],
        [V, 0, 1, V],
        [V, 1, 1, V],
        [V, V, V, V],
      ]),
    );
    expect([out.cols, out.rows]).toEqual([2, 3]);
    expect(out.tiles).toEqual([V, V, 0, 1, 1, 1]);
    const c = (h: number) => ({ h, s: 0, b: 0, c: 0 });
    expect(out.tileColors).toEqual([null, c(10), null, c(14), null, c(18)]);
  });

  it("conserva los muebles colgados por encima del margen y desplaza sus coordenadas", () => {
    const out = trimLayout(
      layout(
        [
          [V, V, V],
          [V, V, V],
          [V, V, V],
          [V, 0, V],
          [V, 1, V],
        ],
        [{ uid: "a", type: "SHELF", col: 1, row: 1 }],
      ),
    );
    expect(out.rows).toBe(4);
    expect(out.furniture).toEqual([{ uid: "a", type: "SHELF", col: 0, row: 0 }]);
  });

  it("devuelve el layout intacto si no hay nada que recortar o si todo está vacío", () => {
    const full = layout([[0, 1], [1, 1]]);
    expect(trimLayout(full)).toBe(full);
    const empty = layout([[V, V], [V, V]]);
    expect(trimLayout(empty)).toBe(empty);
  });
});

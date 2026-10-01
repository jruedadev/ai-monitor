/**
 * El layout por defecto de Pixel Agents trae filas VOID sobrantes y el motor centra
 * la rejilla completa, así que la oficina quedaba desplazada. Recorta los bordes
 * vacíos y desplaza muebles y arrays paralelos en consecuencia.
 */
import { TileType, type OfficeLayout } from "./office/types";

/** Las paredes se dibujan más altas que una baldosa: deja una fila de margen arriba. */
const TOP_MARGIN = 1;

export function trimLayout(layout: OfficeLayout): OfficeLayout {
  const { cols, rows, tiles } = layout;
  let minCol = cols, maxCol = -1, minRow = rows, maxRow = -1;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (tiles[r * cols + c] === TileType.VOID) continue;
      minCol = Math.min(minCol, c);
      maxCol = Math.max(maxCol, c);
      minRow = Math.min(minRow, r);
      maxRow = Math.max(maxRow, r);
    }
  }
  if (maxRow < 0) return layout;
  minRow = Math.max(0, minRow - TOP_MARGIN);
  for (const f of layout.furniture) {
    minRow = Math.min(minRow, Math.max(0, f.row));
    minCol = Math.min(minCol, Math.max(0, f.col));
  }
  const newCols = maxCol - minCol + 1;
  const newRows = maxRow - minRow + 1;
  if (newCols === cols && newRows === rows) return layout;

  const slice = <T>(arr: T[] | undefined): T[] | undefined => {
    if (!arr) return arr;
    const out: T[] = [];
    for (let r = minRow; r <= maxRow; r++) out.push(...arr.slice(r * cols + minCol, r * cols + maxCol + 1));
    return out;
  };

  return {
    ...layout,
    cols: newCols,
    rows: newRows,
    tiles: slice(tiles)!,
    tileColors: slice(layout.tileColors),
    carpetTiles: slice(layout.carpetTiles),
    areaTiles: slice(layout.areaTiles),
    furniture: layout.furniture.map((f) => ({ ...f, col: f.col - minCol, row: f.row - minRow })),
  };
}

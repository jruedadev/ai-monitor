const TILE = 16;
const MIN_ZOOM = 2;

/** Mayor zoom entero ≥ 2 con el que el mapa (cols×rows baldosas de 16 px) cabe en el contenedor. */
export function fitZoom(containerW: number, containerH: number, cols: number, rows: number, dpr: number): number {
  if (cols <= 0 || rows <= 0) return MIN_ZOOM;
  const byW = Math.floor((containerW * dpr) / (cols * TILE));
  const byH = Math.floor((containerH * dpr) / (rows * TILE));
  return Math.max(MIN_ZOOM, Math.min(byW, byH));
}

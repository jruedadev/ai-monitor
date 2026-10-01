/**
 * Carga de assets de la oficina — adaptado de `webview-ui/src/browserMock.ts` de
 * Pixel Agents (MIT, ver LICENSE). Decodifica los PNG en el navegador y registra
 * los sprites en los módulos del motor; en el original esto llegaba por mensajes
 * de la extensión de VS Code.
 */
import { rgbaToHex } from './core/assets/colorUtils.ts';
import {
  CHAR_FRAME_H,
  CHAR_FRAME_W,
  CHAR_FRAMES_PER_ROW,
  CHARACTER_DIRECTIONS,
  FLOOR_TILE_SIZE,
  WALL_BITMASK_COUNT,
  WALL_GRID_COLS,
  WALL_PIECE_HEIGHT,
  WALL_PIECE_WIDTH,
} from './core/assets/constants.ts';
import type {
  AssetIndex,
  CatalogEntry,
  CharacterDirectionSprites,
} from './core/assets/types.ts';
import { setFloorSprites } from './office/floorTiles.js';
import { buildDynamicCatalog, type LoadedAssetData } from './office/layout/furnitureCatalog.js';
import { migrateLayoutColors } from './office/layout/layoutSerializer.js';
import { setCharacterTemplates } from './office/sprites/spriteData.js';
import type { OfficeLayout } from './office/types.js';
import { setWallSprites } from './office/wallTiles.js';

// ── PNG decode helpers (browser fallback) ───────────────────────────────────

interface DecodedPng {
  width: number;
  height: number;
  data: Uint8ClampedArray;
}

function getPixel(
  data: Uint8ClampedArray,
  width: number,
  x: number,
  y: number,
): [number, number, number, number] {
  const idx = (y * width + x) * 4;
  return [data[idx], data[idx + 1], data[idx + 2], data[idx + 3]];
}

function readSprite(
  png: DecodedPng,
  width: number,
  height: number,
  offsetX = 0,
  offsetY = 0,
): string[][] {
  const sprite: string[][] = [];
  for (let y = 0; y < height; y++) {
    const row: string[] = [];
    for (let x = 0; x < width; x++) {
      const [r, g, b, a] = getPixel(png.data, png.width, offsetX + x, offsetY + y);
      row.push(rgbaToHex(r, g, b, a));
    }
    sprite.push(row);
  }
  return sprite;
}

async function decodePng(url: string): Promise<DecodedPng> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch PNG: ${url} (${res.status.toString()})`);
  }
  const blob = await res.blob();
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement('canvas');
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    bitmap.close();
    throw new Error('Failed to create 2d canvas context for PNG decode');
  }
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return { width: canvas.width, height: canvas.height, data: imageData.data };
}

function getIndexedAssetPath(kind: 'characters' | 'floors' | 'walls', relPath: string): string {
  return relPath.startsWith(`${kind}/`) ? relPath : `${kind}/${relPath}`;
}

async function decodeCharactersFromPng(
  base: string,
  index: AssetIndex,
): Promise<CharacterDirectionSprites[]> {
  const sprites: CharacterDirectionSprites[] = [];
  for (const relPath of index.characters) {
    const png = await decodePng(`${base}assets/${getIndexedAssetPath('characters', relPath)}`);
    const byDir: CharacterDirectionSprites = { down: [], up: [], right: [] };

    for (let dirIdx = 0; dirIdx < CHARACTER_DIRECTIONS.length; dirIdx++) {
      const dir = CHARACTER_DIRECTIONS[dirIdx];
      const rowOffsetY = dirIdx * CHAR_FRAME_H;
      const frames: string[][][] = [];
      for (let frame = 0; frame < CHAR_FRAMES_PER_ROW; frame++) {
        frames.push(readSprite(png, CHAR_FRAME_W, CHAR_FRAME_H, frame * CHAR_FRAME_W, rowOffsetY));
      }
      byDir[dir] = frames;
    }

    sprites.push(byDir);
  }
  return sprites;
}

async function decodeFloorsFromPng(base: string, index: AssetIndex): Promise<string[][][]> {
  const floors: string[][][] = [];
  for (const relPath of index.floors) {
    const png = await decodePng(`${base}assets/${getIndexedAssetPath('floors', relPath)}`);
    floors.push(readSprite(png, FLOOR_TILE_SIZE, FLOOR_TILE_SIZE));
  }
  return floors;
}

async function decodeWallsFromPng(base: string, index: AssetIndex): Promise<string[][][][]> {
  const wallSets: string[][][][] = [];
  for (const relPath of index.walls) {
    const png = await decodePng(`${base}assets/${getIndexedAssetPath('walls', relPath)}`);
    const set: string[][][] = [];
    for (let mask = 0; mask < WALL_BITMASK_COUNT; mask++) {
      const ox = (mask % WALL_GRID_COLS) * WALL_PIECE_WIDTH;
      const oy = Math.floor(mask / WALL_GRID_COLS) * WALL_PIECE_HEIGHT;
      set.push(readSprite(png, WALL_PIECE_WIDTH, WALL_PIECE_HEIGHT, ox, oy));
    }
    wallSets.push(set);
  }
  return wallSets;
}

async function decodeFurnitureFromPng(
  base: string,
  catalog: CatalogEntry[],
): Promise<Record<string, string[][]>> {
  const sprites: Record<string, string[][]> = {};
  for (const entry of catalog) {
    const png = await decodePng(`${base}assets/${entry.furniturePath}`);
    sprites[entry.id] = readSprite(png, entry.width, entry.height);
  }
  return sprites;
}

// ── API pública ───────────────────────────────────────────────────────────────

export interface LoadedOffice {
  layout: OfficeLayout | null;
}

/** Decodifica y registra todos los sprites. `base` termina en '/', p. ej. '/pixel/'. */
export async function loadOfficeAssets(base: string): Promise<LoadedOffice> {
  const [assetIndex, catalog] = await Promise.all([
    fetch(`${base}assets/asset-index.json`).then((r) => r.json()) as Promise<AssetIndex>,
    fetch(`${base}assets/furniture-catalog.json`).then((r) => r.json()) as Promise<CatalogEntry[]>,
  ]);
  const [characters, floorSprites, wallSets, furnitureSprites] = await Promise.all([
    decodeCharactersFromPng(base, assetIndex),
    decodeFloorsFromPng(base, assetIndex),
    decodeWallsFromPng(base, assetIndex),
    decodeFurnitureFromPng(base, catalog),
  ]);
  // Mismo orden que el original: personajes → suelos → paredes → muebles → layout.
  setCharacterTemplates(characters);
  setFloorSprites(floorSprites);
  setWallSprites(wallSets);
  buildDynamicCatalog({ catalog: catalog as unknown as LoadedAssetData['catalog'], sprites: furnitureSprites });
  const raw = assetIndex.defaultLayout
    ? ((await fetch(`${base}assets/${assetIndex.defaultLayout}`).then((r) => r.json())) as OfficeLayout)
    : null;
  return { layout: raw && raw.version === 1 ? migrateLayoutColors(raw) : null };
}

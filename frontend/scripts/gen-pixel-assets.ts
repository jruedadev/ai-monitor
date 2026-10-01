/**
 * Regenera public/pixel/assets/asset-index.json y furniture-catalog.json a partir de las carpetas
 * de assets. Uso: `npx tsx scripts/gen-pixel-assets.ts` desde frontend/.
 */
import { readdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const ASSETS = join(import.meta.dirname, "..", "public", "pixel", "assets");
const pngs = (dir: string) => readdirSync(join(ASSETS, dir)).filter((f) => f.endsWith(".png")).sort();

const index = {
  floors: pngs("floors"),
  walls: pngs("walls"),
  characters: pngs("characters"),
  defaultLayout: "default-layout-1.json",
};
writeFileSync(join(ASSETS, "asset-index.json"), JSON.stringify(index));

type Member = Record<string, unknown>;
const catalog: Record<string, unknown>[] = [];
for (const dir of readdirSync(join(ASSETS, "furniture")).sort()) {
  const manifestPath = join(ASSETS, "furniture", dir, "manifest.json");
  if (!existsSync(manifestPath)) continue;
  const m = JSON.parse(readFileSync(manifestPath, "utf8")) as Member & { members?: Member[] };
  const base = (id: unknown, file: unknown, w: unknown, h: unknown, fw: unknown, fh: unknown) => ({
    id, name: m.name, label: m.name, category: m.category, file, width: w, height: h,
    footprintW: fw, footprintH: fh, isDesk: m.category === "desks",
    canPlaceOnWalls: m.canPlaceOnWalls, canPlaceOnSurfaces: m.canPlaceOnSurfaces,
    backgroundTiles: m.backgroundTiles, groupId: m.id,
  });
  if (m.type === "group" && m.members) {
    // Los grupos se anidan (rotación → estado → animación): se aplanan heredando orientación y estado.
    const walk = (members: Member[], inherited: Member) => {
      for (const mem of members) {
        const ctx: Member = { ...inherited };
        if (mem.orientation !== undefined) ctx.orientation = mem.orientation;
        if (mem.state !== undefined) ctx.state = mem.state;
        if (mem.type === "group" && Array.isArray(mem.members)) {
          if (mem.groupType === "animation") {
            ctx.animationGroup = `${m.id}_${String(ctx.orientation).toUpperCase()}_${String(ctx.state).toUpperCase()}`;
          }
          walk(mem.members as Member[], ctx);
          continue;
        }
        catalog.push({
          ...base(mem.id, mem.file, mem.width, mem.height, mem.footprintW, mem.footprintH),
          orientation: ctx.orientation,
          ...(ctx.state !== undefined ? { state: ctx.state } : {}),
          ...(mem.mirrorSide ? { mirrorSide: true } : {}),
          rotationScheme: m.rotationScheme,
          ...(ctx.animationGroup !== undefined ? { animationGroup: ctx.animationGroup, frame: mem.frame } : {}),
          furniturePath: `furniture/${dir}/${mem.file}`,
        });
      }
    };
    walk(m.members, {});
  } else {
    catalog.push({
      ...base(m.id, `${m.id}.png`, m.width, m.height, m.footprintW, m.footprintH),
      furniturePath: `furniture/${dir}/${m.id}.png`,
    });
  }
}
writeFileSync(join(ASSETS, "furniture-catalog.json"), JSON.stringify(catalog));
console.log(`asset-index.json y furniture-catalog.json (${catalog.length} muebles) regenerados`);

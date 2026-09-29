import {
  errorDetail, type AppSettings, type AvailableBackends, type EngineBackend, type EngineSettings, type RoiSettings,
} from "@/lib/api";
import { DEFAULT_CLIENT_ROOTS, type ClientRoot } from "@/lib/clients";
import { parsePath } from "@/lib/routes";

export interface OnboardingGate {
  loading: boolean;
  error: string | null;
  degraded: boolean;
  completedAt: string | null;
}

/** Solo redirige si el servidor confirmó que falta el onboarding: un error nunca atrapa al usuario. */
export function shouldRedirectToOnboarding(gate: OnboardingGate, pathname: string): boolean {
  if (gate.loading || gate.error || gate.degraded || gate.completedAt !== null) return false;
  return parsePath(pathname)?.view !== "onboarding";
}

const MAX_SUGGESTED = 3;
const HOME_DIRS = new Set(["home", "users"]);

/** Carpeta dos niveles arriba de cada proyecto (/x/DEV/ACME/app → DEV) repetida en ≥2 proyectos. */
export function suggestRoots(paths: string[]): ClientRoot[] {
  const counts = new Map<string, { name: string; count: number }>();
  for (const path of paths) {
    const segments = path.split("/");
    const idx = segments.length - 3;
    if (idx < 1) continue;
    const name = segments[idx];
    if (!name || name.startsWith(".") || HOME_DIRS.has(name.toLowerCase()) || HOME_DIRS.has(segments[idx - 1].toLowerCase())) continue;
    const key = name.toUpperCase();
    const entry = counts.get(key) ?? { name, count: 0 };
    entry.count += 1;
    counts.set(key, entry);
  }
  const ranked = [...counts.values()]
    .filter((e) => e.count >= 2)
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .slice(0, MAX_SUGGESTED);
  return ranked.length > 0
    ? ranked.map((e) => ({ root: e.name, mode: "cliente" as const }))
    : DEFAULT_CLIENT_ROOTS.map((r) => ({ ...r }));
}

export function suggestBackend(available: AvailableBackends): EngineBackend {
  if (available.hermes) return "hermes";
  if (available.claude) return "claude";
  return "none";
}

export type OnboardingStep = "folders" | "roi" | "engine";
export const ONBOARDING_STEPS: OnboardingStep[] = ["folders", "roi", "engine"];

export interface OnboardingDraft {
  roots: ClientRoot[];
  /** null = no tocar los ajustes de ROI (Omitir). */
  roi: Partial<RoiSettings> | null;
  engine: EngineSettings;
}

export interface OnboardingApi {
  saveAppSettings: (s: { client_roots: ClientRoot[] }) => Promise<AppSettings | unknown>;
  saveRoiSettings: (s: Partial<RoiSettings>) => Promise<unknown>;
  saveEngineSettings: (s: EngineSettings) => Promise<unknown>;
  completeOnboarding: () => Promise<unknown>;
}

export type SaveResult = { ok: true } | { ok: false; step: OnboardingStep; message: string };

const GENERIC_ERROR = "No se pudo guardar. Revisa que el servidor siga activo e inténtalo de nuevo.";

/** Guarda en orden y marca el onboarding al final. Cada guardado es idempotente: reintentar es seguro. */
export async function saveOnboarding(draft: OnboardingDraft, api: OnboardingApi): Promise<SaveResult> {
  const steps: [OnboardingStep, () => Promise<unknown>][] = [
    ["folders", () => api.saveAppSettings({ client_roots: draft.roots })],
    ...(draft.roi ? [["roi", () => api.saveRoiSettings(draft.roi as Partial<RoiSettings>)] as [OnboardingStep, () => Promise<unknown>]] : []),
    ["engine", () => api.saveEngineSettings(draft.engine)],
    ["engine", () => api.completeOnboarding()],
  ];
  for (const [step, run] of steps) {
    try {
      await run();
    } catch (err) {
      return { ok: false, step, message: errorDetail(err) ?? GENERIC_ERROR };
    }
  }
  return { ok: true };
}

export function skipDraft(available: AvailableBackends, llmChain: string[]): OnboardingDraft {
  return {
    roots: DEFAULT_CLIENT_ROOTS.map((r) => ({ ...r })),
    roi: null,
    engine: { backend: suggestBackend(available), llm_chain: llmChain },
  };
}

/** Qué hace "Omitir": la primera vez guarda los valores por defecto; al repetir la
 * configuración (null) sale sin tocar nada de lo ya guardado (spec §4.3). */
export function skipOutcome(completedAt: string | null, available: AvailableBackends, llmChain: string[]): OnboardingDraft | null {
  return completedAt === null ? skipDraft(available, llmChain) : null;
}

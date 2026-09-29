import type { RoiSettings } from "@/lib/api";
import type { SourceStatus } from "@/lib/settings";

/** Borrador de formulario: todo como texto; "" = sin valor. */
export type RoiDraft = Record<keyof RoiSettings, string>;
export type RoiPlan = "claude" | "codex";

export function toRoiDraft(s: RoiSettings): RoiDraft {
  return {
    subscription_cost_claude: s.subscription_cost_claude?.toString() ?? "",
    subscription_cost_codex: s.subscription_cost_codex?.toString() ?? "",
    hourly_rate: s.hourly_rate?.toString() ?? "",
    subscription_start_claude: s.subscription_start_claude ?? "",
    subscription_start_codex: s.subscription_start_codex ?? "",
  };
}

export function roiPayload(d: RoiDraft): Partial<RoiSettings> {
  return {
    subscription_cost_claude: d.subscription_cost_claude ? Number(d.subscription_cost_claude) : null,
    subscription_cost_codex: d.subscription_cost_codex ? Number(d.subscription_cost_codex) : null,
    hourly_rate: d.hourly_rate ? Number(d.hourly_rate) : null,
    subscription_start_claude: d.subscription_start_claude || null,
    subscription_start_codex: d.subscription_start_codex || null,
  };
}

/** Planes con suscripción que tiene sentido pedir: los de fuentes con datos. */
export function plansWithData(statuses: SourceStatus[]): RoiPlan[] {
  const withData = new Set(statuses.filter((s) => s.state === "data").map((s) => s.key));
  return (["claude", "codex"] as const).filter((plan) => withData.has(plan === "claude" ? "claude_code" : "codex"));
}

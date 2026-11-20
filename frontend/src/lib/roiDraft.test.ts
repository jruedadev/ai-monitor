import { describe, expect, it } from "vitest";
import {
  addAccountDraft, plansWithData, removeAccountDraft, roiPayload, toRoiDraft, validateAccountDrafts,
  type AccountDraft,
} from "@/lib/roiDraft";
import type { SourceStatus } from "@/lib/settings";

describe("roiDraft", () => {
  it("ida y vuelta: vacíos → null, números → number", () => {
    const draft = toRoiDraft({
      subscription_cost_claude: 20, subscription_cost_codex: null, hourly_rate: 35,
      subscription_start_claude: "2026-07-18", subscription_start_codex: null,
    });
    expect(draft).toEqual({
      subscription_cost_claude: "20", subscription_cost_codex: "", hourly_rate: "35",
      subscription_start_claude: "2026-07-18", subscription_start_codex: "",
    });
    expect(roiPayload(draft)).toEqual({
      subscription_cost_claude: 20, subscription_cost_codex: null, hourly_rate: 35,
      subscription_start_claude: "2026-07-18", subscription_start_codex: null,
    });
  });

  it("plansWithData: solo planes de fuentes con datos", () => {
    const st = (key: SourceStatus["key"], state: SourceStatus["state"]) => ({ key, label: key, state, detail: "" });
    expect(plansWithData([st("claude_code", "data"), st("codex", "empty"), st("hermes", "data")])).toEqual(["claude"]);
    expect(plansWithData([st("claude_code", "empty"), st("codex", "data")])).toEqual(["codex"]);
    expect(plansWithData([])).toEqual([]);
  });
});

const acc = (over: Partial<AccountDraft> = {}): AccountDraft => ({
  id: "personal", provider: "claude_code", label: "Personal", location: "/home/u/.claude",
  default: true, monthly_cost: 20, start_date: "2026-07-18", ...over,
});

describe("cuentas", () => {
  const two = [acc(), acc({ id: "trabajo", label: "Trabajo", location: "/home/u/.claude-work", default: false })];

  it("validateAccountDrafts: dos cuentas con un solo default son válidas", () => {
    expect(validateAccountDrafts(two)).toBeNull();
  });

  it("validateAccountDrafts: rechaza lo que el backend rechaza, en español", () => {
    expect(validateAccountDrafts([acc(), acc({ id: "b" })])).toMatch(/por defecto/);
    expect(validateAccountDrafts([acc({ default: false })])).toMatch(/por defecto/);
    expect(validateAccountDrafts([acc({ id: "" })])).toMatch(/id/i);
    expect(validateAccountDrafts([acc(), acc({ default: false })])).toMatch(/repetid/);
    expect(validateAccountDrafts([acc({ location: "relativa/.claude" })])).toMatch(/ruta absoluta/);
    expect(validateAccountDrafts([acc({ label: "  " })])).toMatch(/nombre/i);
    expect(validateAccountDrafts([acc({ monthly_cost: -1 })])).toMatch(/costo/i);
  });

  it("addAccountDraft: añade una cuenta no default con id que no colisiona", () => {
    const once = addAccountDraft(two, "claude_code");
    expect(once).toHaveLength(3);
    const added = once[2];
    expect(added.default).toBe(false);
    expect(added.provider).toBe("claude_code");
    const twice = addAccountDraft(once, "claude_code");
    expect(new Set(twice.map((a) => a.id)).size).toBe(4);
  });

  it("removeAccountDraft: quita una cuenta normal, pero no la única default", () => {
    expect(removeAccountDraft(two, "trabajo").map((a) => a.id)).toEqual(["personal"]);
    expect(removeAccountDraft(two, "personal")).toBe(two);
  });
});

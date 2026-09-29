import { describe, expect, it } from "vitest";
import { plansWithData, roiPayload, toRoiDraft } from "@/lib/roiDraft";
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

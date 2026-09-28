import { describe, expect, it } from "vitest";
import cases from "../../../tests/fixtures/client_of_cases.json";
import { clientOf } from "@/lib/clients";

describe("clientOf: paridad con briefing.client_of (fixture compartido)", () => {
  it.each(cases)("$path → $client", ({ path, client }) => {
    expect(clientOf(path)).toBe(client);
  });
});

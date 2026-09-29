import { describe, expect, it } from "vitest";
import cases from "../../../tests/fixtures/client_of_cases.json";
import { DEFAULT_CLIENT_ROOTS, clientOf, groupProjectsByClient, previewClients, type ClientRoot } from "@/lib/clients";

describe("clientOf: paridad con clients.client_of (fixture compartido)", () => {
  it.each(cases)("$path con $roots → $client", ({ roots, path, client }) => {
    expect(clientOf(path, (roots as ClientRoot[] | null) ?? DEFAULT_CLIENT_ROOTS)).toBe(client);
  });
});

describe("groupProjectsByClient", () => {
  it("agrupa según las raíces dadas", () => {
    const roots: ClientRoot[] = [{ root: "/srv/trabajo", mode: "plano" }];
    expect(groupProjectsByClient(["/srv/trabajo/a", "/srv/trabajo/b", "/tmp/c"], roots)).toEqual({
      trabajo: ["/srv/trabajo/a", "/srv/trabajo/b"],
      Otros: ["/tmp/c"],
    });
  });
});

describe("previewClients", () => {
  it("cuenta proyectos por cliente, separa Otros e ignora raíces vacías", () => {
    const roots: ClientRoot[] = [{ root: "DEV", mode: "cliente" }, { root: "  ", mode: "cliente" }];
    expect(previewClients(["/h/DEV/A/x", "/h/DEV/A/y", "/h/DEV/B/z", "/tmp/q"], roots)).toEqual({
      clients: [{ name: "A", count: 2 }, { name: "B", count: 1 }],
      other: 1,
    });
  });
  it("sin raíces útiles todo cae en Otros", () => {
    expect(previewClients(["/a/b"], [{ root: "", mode: "plano" }])).toEqual({ clients: [], other: 1 });
  });
});

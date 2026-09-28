import { describe, expect, it } from "vitest";
import { formatCompact, formatDate, formatDayShort, formatInt, formatMonth, formatUsd } from "@/lib/format";

// Intl usa espacios no separables; se normalizan para comparar.
const norm = (text: string) => text.replace(/\s/g, " ");

describe("números es-CO", () => {
  it("agrupa miles con punto, también en 4 cifras", () => {
    expect(formatInt(1234)).toBe("1.234");
  });

  it("USD con símbolo corto y coma decimal", () => {
    expect(norm(formatUsd(79514.234))).toBe("$ 79.514,23");
  });

  it("compacto", () => {
    expect(norm(formatCompact(70_200_000))).toBe("70,2 M");
  });
});

describe("fechas", () => {
  it("mes: solo la primera letra en mayúscula", () => {
    expect(formatMonth("2026-04")).toBe("Abril de 2026");
  });

  it("día corto sin 'de' ni punto", () => {
    expect(norm(formatDayShort("2026-07-18"))).toBe("18 jul");
  });

  it("no retrocede un día por la zona horaria", () => {
    expect(norm(formatDate("2026-01-01"))).toBe("1 ene 2026");
  });
});

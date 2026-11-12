import { describe, expect, it } from "vitest";
import { calculateSaleLineQuote, sumSaleLineTotals } from "./sale";

const product = {
  retail_price: "200.00",
  wholesale_price: "180.00",
  price_tiers: [
    { price_type: "retail" as const, minimum_quantity: "5", unit_price: "175.00" },
    { price_type: "wholesale" as const, minimum_quantity: "10", unit_price: "160.00" },
  ],
};

describe("calculateSaleLineQuote", () => {
  it("uses the selected sale type and eligible quantity tier", () => {
    expect(calculateSaleLineQuote(product, "retail", "2")).toEqual({
      unitPrice: "200.00",
      lineTotal: "400.00",
    });
    expect(calculateSaleLineQuote(product, "retail", "5")).toEqual({
      unitPrice: "175.00",
      lineTotal: "875.00",
    });
    expect(calculateSaleLineQuote(product, "wholesale", "10")).toEqual({
      unitPrice: "160.00",
      lineTotal: "1600.00",
    });
  });

  it("uses decimal-safe line total rounding and rejects invalid quantities", () => {
    expect(calculateSaleLineQuote({
      ...product,
      retail_price: "1.00",
      price_tiers: [],
    }, "retail", "0.015")).toEqual({ unitPrice: "1.00", lineTotal: "0.02" });
    expect(calculateSaleLineQuote(product, "retail", "0")).toBeNull();
    expect(calculateSaleLineQuote(product, "retail", "invalid")).toBeNull();
  });
});

describe("sumSaleLineTotals", () => {
  it("adds line totals without floating point loss and waits for complete lines", () => {
    expect(sumSaleLineTotals(["1250.10", "0.20", "0.70"])).toBe("1251.00");
    expect(sumSaleLineTotals(["100.00", null])).toBeNull();
  });
});

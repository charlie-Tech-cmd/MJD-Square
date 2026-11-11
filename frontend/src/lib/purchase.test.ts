import { describe, expect, it } from "vitest";
import { calculatePurchaseLineTotal, sumMoney } from "./purchase";

describe("calculatePurchaseLineTotal", () => {
  it("multiplies supplied quantity by unit cost using decimal-safe arithmetic", () => {
    expect(calculatePurchaseLineTotal("2.5", "1250.40")).toBe("3126.00");
    expect(calculatePurchaseLineTotal("3", "0.25")).toBe("0.75");
  });

  it("uses half-even rounding to match the backend's monetary quantization", () => {
    expect(calculatePurchaseLineTotal("0.005", "1.00")).toBe("0.00");
    expect(calculatePurchaseLineTotal("0.015", "1.00")).toBe("0.02");
  });

  it("returns no preview for invalid or non-positive quantities", () => {
    expect(calculatePurchaseLineTotal("", "100.00")).toBeNull();
    expect(calculatePurchaseLineTotal("0", "100.00")).toBeNull();
    expect(calculatePurchaseLineTotal("1", "1.001")).toBeNull();
  });
});

describe("sumMoney", () => {
  it("adds invoice totals without floating point loss", () => {
    expect(sumMoney(["1250.10", "0.20", "0.70"])).toBe("1251.00");
  });
});

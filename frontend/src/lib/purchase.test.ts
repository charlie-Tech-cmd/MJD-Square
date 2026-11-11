import { describe, expect, it } from "vitest";
import {
  calculatePurchaseLineTotal,
  filterPurchaseHistory,
  getPurchaseFilterError,
  hasPurchaseHistoryFilters,
  sumMoney,
  type PurchaseHistoryFilters,
} from "./purchase";
import type { Purchase } from "../types";

const defaultFilters: PurchaseHistoryFilters = {
  fromDate: "",
  toDate: "",
  product: "",
  minAmount: "",
  maxAmount: "",
  order: "",
  paymentStatus: "all",
};

const purchases: Purchase[] = [
  {
    id: "purchase-1",
    purchase_number: "PUR-100",
    supplier_id: "supplier-1",
    supplier_name: "Emeka",
    supplier_reference: "ORDER-ABC",
    purchase_date: "2026-11-09",
    lines: [{
      product_id: "product-1",
      product_name: "Coca Cola",
      sku: "DRINK-01",
      unit_name: "Pack",
      quantity: "1",
      unit_cost: "450.00",
      line_total: "450.00",
    }],
    total_amount: "450.00",
    amount_paid: "0.00",
    balance_due: "450.00",
    payments: [],
    notes: "",
    created_at: "2026-11-09T10:00:00",
  },
  {
    id: "purchase-2",
    purchase_number: "PUR-200",
    supplier_id: "supplier-2",
    supplier_name: "Ada",
    supplier_reference: null,
    purchase_date: "2026-11-10",
    lines: [{
      product_id: "product-2",
      product_name: "Rice",
      sku: "FOOD-02",
      unit_name: "Bag",
      quantity: "2",
      unit_cost: "1000.00",
      line_total: "2000.00",
    }],
    total_amount: "2000.00",
    amount_paid: "2000.00",
    balance_due: "0.00",
    payments: [],
    notes: "",
    created_at: "2026-11-10T10:00:00",
  },
];

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

describe("filterPurchaseHistory", () => {
  it("filters by inclusive dates, product, amount, order reference, and payment status", () => {
    expect(filterPurchaseHistory(purchases, {
      ...defaultFilters,
      fromDate: "2026-11-09",
      toDate: "2026-11-09",
      product: "coca",
      minAmount: "400.00",
      maxAmount: "500.00",
      order: "order-abc",
      paymentStatus: "outstanding",
    }).map((purchase) => purchase.id)).toEqual(["purchase-1"]);
  });

  it("matches product SKU and invoice number", () => {
    expect(filterPurchaseHistory(purchases, {
      ...defaultFilters,
      product: "food-02",
      order: "pur-200",
    }).map((purchase) => purchase.id)).toEqual(["purchase-2"]);
  });

  it("returns an error for invalid date or amount ranges", () => {
    expect(getPurchaseFilterError({
      ...defaultFilters,
      fromDate: "2026-11-10",
      toDate: "2026-11-09",
    })).toContain("start date");
    expect(getPurchaseFilterError({
      ...defaultFilters,
      minAmount: "500.00",
      maxAmount: "400.00",
    })).toContain("minimum amount");
  });

  it("tracks active filters and supports a cleared state", () => {
    expect(hasPurchaseHistoryFilters(defaultFilters)).toBe(false);
    expect(hasPurchaseHistoryFilters({ ...defaultFilters, paymentStatus: "paid" })).toBe(true);
    expect(filterPurchaseHistory(purchases, defaultFilters)).toHaveLength(2);
  });
});

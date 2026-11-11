import type { Purchase } from "../types";

function parseScaledInteger(value: string, decimalPlaces: number, pattern: RegExp): bigint | null {
  if (!pattern.test(value)) return null;
  const [whole = "0", fraction = ""] = value.split(".");
  return BigInt(whole) * 10n ** BigInt(decimalPlaces)
    + BigInt(fraction.padEnd(decimalPlaces, "0"));
}

function roundHalfEven(numerator: bigint, denominator: bigint): bigint {
  const quotient = numerator / denominator;
  const remainder = numerator % denominator;
  const doubledRemainder = remainder * 2n;
  if (doubledRemainder < denominator) return quotient;
  if (doubledRemainder > denominator || quotient % 2n !== 0n) return quotient + 1n;
  return quotient;
}

function centsToMoney(cents: bigint): string {
  return `${cents / 100n}.${(cents % 100n).toString().padStart(2, "0")}`;
}

export function calculatePurchaseLineTotal(quantity: string, unitCost: string): string | null {
  const quantityMilliunits = parseScaledInteger(
    quantity,
    3,
    /^\d{1,11}(?:\.\d{1,3})?$/,
  );
  const unitCostCents = parseScaledInteger(
    unitCost,
    2,
    /^\d{1,12}(?:\.\d{1,2})?$/,
  );
  if (quantityMilliunits === null || quantityMilliunits <= 0n || unitCostCents === null) {
    return null;
  }
  return centsToMoney(roundHalfEven(quantityMilliunits * unitCostCents, 1000n));
}

export function sumMoney(values: string[]): string {
  const cents = values.reduce((total, value) => {
    const parsed = parseScaledInteger(value, 2, /^\d{1,12}(?:\.\d{1,2})?$/);
    if (parsed === null) throw new RangeError("Invalid monetary amount.");
    return total + parsed;
  }, 0n);
  return centsToMoney(cents);
}

export interface PurchaseHistoryFilters {
  fromDate: string;
  toDate: string;
  product: string;
  minAmount: string;
  maxAmount: string;
  order: string;
  paymentStatus: "all" | "outstanding" | "paid";
}

function parseAmountCents(value: string): bigint | null {
  return parseScaledInteger(value, 2, /^\d{1,12}(?:\.\d{1,2})?$/);
}

export function getPurchaseFilterError(filters: PurchaseHistoryFilters): string | null {
  if (filters.fromDate && filters.toDate && filters.fromDate > filters.toDate) {
    return "The start date must be on or before the end date.";
  }
  if (filters.minAmount && parseAmountCents(filters.minAmount) === null) {
    return "Enter a valid minimum amount with up to 2 decimal places.";
  }
  if (filters.maxAmount && parseAmountCents(filters.maxAmount) === null) {
    return "Enter a valid maximum amount with up to 2 decimal places.";
  }
  const minimum = filters.minAmount ? parseAmountCents(filters.minAmount) : null;
  const maximum = filters.maxAmount ? parseAmountCents(filters.maxAmount) : null;
  if (minimum !== null && maximum !== null && minimum > maximum) {
    return "The minimum amount cannot exceed the maximum amount.";
  }
  return null;
}

export function filterPurchaseHistory(
  purchases: Purchase[],
  filters: PurchaseHistoryFilters,
): Purchase[] {
  const minimum = filters.minAmount ? parseAmountCents(filters.minAmount) : null;
  const maximum = filters.maxAmount ? parseAmountCents(filters.maxAmount) : null;
  if (getPurchaseFilterError(filters)) return [];

  const productQuery = filters.product.trim().toLocaleLowerCase();
  const orderQuery = filters.order.trim().toLocaleLowerCase();
  return purchases.filter((purchase) => {
    if (filters.fromDate && purchase.purchase_date < filters.fromDate) return false;
    if (filters.toDate && purchase.purchase_date > filters.toDate) return false;
    if (filters.paymentStatus === "paid" && purchase.balance_due !== "0.00") return false;
    if (filters.paymentStatus === "outstanding" && purchase.balance_due === "0.00") return false;
    if (minimum !== null || maximum !== null) {
      const amount = parseAmountCents(purchase.total_amount);
      if (amount === null) throw new RangeError("Invalid purchase total amount.");
      if (minimum !== null && amount < minimum) return false;
      if (maximum !== null && amount > maximum) return false;
    }
    if (productQuery && !purchase.lines.some((line) => (
      `${line.product_name} ${line.sku}`.toLocaleLowerCase().includes(productQuery)
    ))) return false;
    if (orderQuery && !(
      `${purchase.purchase_number} ${purchase.supplier_reference ?? ""} ${purchase.supplier_name ?? ""} ${purchase.notes}`
        .toLocaleLowerCase()
        .includes(orderQuery)
    )) return false;
    return true;
  });
}

export function hasPurchaseHistoryFilters(filters: PurchaseHistoryFilters): boolean {
  return Boolean(
    filters.fromDate
    || filters.toDate
    || filters.product.trim()
    || filters.minAmount
    || filters.maxAmount
    || filters.order.trim()
    || filters.paymentStatus !== "all",
  );
}

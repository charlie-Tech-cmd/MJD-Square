import type { Product, ProductPriceTier } from "../types";

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

export interface SaleLineQuote {
  unitPrice: string;
  lineTotal: string;
}

export function calculateSaleLineQuote(
  product: Pick<Product, "retail_price" | "wholesale_price" | "price_tiers">,
  saleType: "retail" | "wholesale",
  quantity: string,
): SaleLineQuote | null {
  const quantityMilliunits = parseScaledInteger(quantity, 3, /^\d{1,11}(?:\.\d{1,3})?$/);
  if (quantityMilliunits === null || quantityMilliunits <= 0n) return null;

  const eligibleTiers = product.price_tiers
    .map((tier) => ({
      tier,
      minimum: parseScaledInteger(
        tier.minimum_quantity,
        3,
        /^\d{1,11}(?:\.\d{1,3})?$/,
      ),
    }))
    .filter((entry): entry is { tier: ProductPriceTier; minimum: bigint } => (
      entry.tier.price_type === saleType
      && entry.minimum !== null
      && quantityMilliunits >= entry.minimum
    ))
    .sort((first, second) => first.minimum < second.minimum ? 1 : -1);
  const unitPrice = eligibleTiers[0]?.tier.unit_price
    ?? (saleType === "retail" ? product.retail_price : product.wholesale_price);
  const unitPriceCents = parseScaledInteger(unitPrice, 2, /^\d{1,12}(?:\.\d{1,2})?$/);
  if (unitPriceCents === null) return null;

  return {
    unitPrice,
    lineTotal: centsToMoney(roundHalfEven(quantityMilliunits * unitPriceCents, 1000n)),
  };
}

export function sumSaleLineTotals(values: (string | null)[]): string | null {
  if (values.some((value) => value === null)) return null;
  const totalCents = values.reduce((total, value) => {
    const cents = parseScaledInteger(value ?? "", 2, /^\d{1,12}(?:\.\d{1,2})?$/);
    if (cents === null) throw new RangeError("Invalid sale line total.");
    return total + cents;
  }, 0n);
  return centsToMoney(totalCents);
}

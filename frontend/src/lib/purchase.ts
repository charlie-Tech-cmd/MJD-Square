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

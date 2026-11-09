export function formatNaira(value: string): string {
  const [wholePart, fractionPart = ""] = value.split(".");
  const whole = BigInt(wholePart || "0");
  const fraction = fractionPart.padEnd(2, "0").slice(0, 2);
  return `₦${new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 }).format(whole)}.${fraction}`;
}

export function formatQuantity(value: string, decimalPlaces: number): string {
  const [wholePart, fractionPart = ""] = value.split(".");
  const whole = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 }).format(
    BigInt(wholePart || "0"),
  );
  const fraction = fractionPart.slice(0, decimalPlaces).replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : whole;
}

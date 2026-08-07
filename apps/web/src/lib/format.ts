import type { Material } from "../types/material";

/** Trim the trailing zeros a fixed-precision string leaves behind: 72.000 -> 72. */
function trimZeros(fixed: string): string {
  return fixed.replace(/0+$/, "").replace(/\.$/, "");
}

export function formatNumber(value: unknown, digits = 3): string {
  return typeof value === "number" && Number.isFinite(value) ? trimZeros(value.toFixed(digits)) : "n/a";
}

/** Like formatNumber, but passes strings through and stringifies anything else. */
export function formatUnknown(value: unknown, fallback = "n/a", digits = 3): string {
  if (value === null || value === undefined) {
    return fallback;
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : trimZeros(value.toFixed(digits));
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

export function formatValue(value: unknown, unit?: string | null): string {
  const formatted = formatUnknown(value, "unknown", 4);
  return unit ? `${formatted} ${unit}` : formatted;
}

/** Numeric value of a named property, or null when absent or non-numeric. */
export function propertyNumber(material: Material, name: string): number | null {
  const property = (material.properties ?? []).find((entry) => entry.name === name);
  return typeof property?.value === "number" ? property.value : null;
}

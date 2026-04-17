
export function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

export function formatNumber(value: unknown, digits = 2): string {
  const num = asNumber(value);
  if (num === null) return "N/A";
  return num.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPercent(value: unknown, digits = 2): string {
  const num = asNumber(value);
  if (num === null) return "N/A";
  return `${formatNumber(num, digits)}%`;
}

export function formatAnyNumber(value: unknown, digits = 2): string {
  const num = asNumber(value);
  if (num === null) return String(value ?? "N/A");
  return formatNumber(num, digits);
}

export function formatCurrency(value: unknown, digits = 2, currencySymbol = "$", compact = false): string {
  const num = asNumber(value);
  if (num === null) return "N/A";
  if (compact) {
    const abs = Math.abs(num);
    if (abs >= 1_000_000_000) return `${currencySymbol}${formatNumber(num / 1_000_000_000, digits)}B`;
    if (abs >= 1_000_000) return `${currencySymbol}${formatNumber(num / 1_000_000, digits)}M`;
    if (abs >= 1_000) return `${currencySymbol}${formatNumber(num / 1_000, digits)}K`;
  }
  return `${currencySymbol}${formatNumber(num, digits)}`;
}

export function formatMaybeDate(value: unknown): string {
  if (!value) return "-";
  return String(value);
}

/** 通用格式化与校验工具。 */

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export function parseApiDate(value: string): Date {
  // SQLAlchemy stores UTC timestamps without an offset; mark them as UTC before browser conversion.
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

export function formatDate(iso: string): string {
  if (!iso) return "";
  return parseApiDate(iso).toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatDateTime(iso: string): string {
  if (!iso) return "-";
  return parseApiDate(iso).toLocaleString("zh-CN", { hour12: false });
}

export function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function bucketPct(count: number, buckets: { count: number }[]) {
  const max = Math.max(1, ...buckets.map((item) => item.count));
  return `${Math.max(4, Math.round((count / max) * 100))}%`;
}

export function completionRate(value: number | undefined) {
  return `${Math.round((value || 0) * 100)}%`;
}

const EMPTY_TEXT = "资料待补充";

/** @param {string | number | Date} value @param {string} locale */
export function formatDate(value, locale = "zh-CN") {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? EMPTY_TEXT
    : new Intl.DateTimeFormat(locale, { year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

/** @param {string | number | Date} value @param {string} locale */
export function formatTime(value, locale = "zh-CN") {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? EMPTY_TEXT
    : new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

/** @param {string | number} value @param {string} currency @param {string} locale */
export function formatMoney(value, currency = "CNY", locale = "zh-CN") {
  const amount = Number(value);
  return Number.isFinite(amount)
    ? new Intl.NumberFormat(locale, { style: "currency", currency }).format(amount)
    : EMPTY_TEXT;
}

/** @param {string | number} value @param {number} digits @param {string} locale */
export function formatPercent(value, digits = 0, locale = "zh-CN") {
  const percentage = Number(value);
  return Number.isFinite(percentage)
    ? new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: digits }).format(percentage)
    : EMPTY_TEXT;
}

/** @param {unknown} value */
export function formatUserName(value) {
  const name = typeof value === "string" ? value.trim() : "";
  return name || "未设置名称";
}

/** @param {unknown} value @param {string} fallback */
export function formatEmpty(value, fallback = EMPTY_TEXT) {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string" && !value.trim()) return fallback;
  return String(value);
}

/** @param {unknown} value @param {Record<string, string>} labels */
export function formatStatus(value, labels = {}) {
  const key = String(value ?? "");
  return labels[key] || formatEmpty(value, "状态未知");
}

/** @param {unknown} value @param {number} maxLength */
export function truncateText(value, maxLength = 80) {
  const text = formatEmpty(value, "");
  return text.length > maxLength ? `${text.slice(0, Math.max(0, maxLength - 1))}…` : text;
}

/** @param {{displayValue?: string, value?: number, suffix?: string}} metric */
export function formatMetric(metric) {
  if (metric.displayValue) return metric.displayValue;
  const value = metric.value;
  if (typeof value !== "number" || !Number.isFinite(value)) return EMPTY_TEXT;
  return `${new Intl.NumberFormat("zh-CN").format(value)}${metric.suffix || ""}`;
}

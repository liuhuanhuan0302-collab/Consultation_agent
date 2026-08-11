const TAB_KEYS = new Set(["ArrowLeft", "ArrowRight", "Home", "End"]);

/**
 * @param {number} currentIndex
 * @param {number} total
 * @param {string} key
 */
export function getNextTabIndex(currentIndex, total, key) {
  if (!TAB_KEYS.has(key) || total <= 0) return currentIndex;
  if (key === "Home") return 0;
  if (key === "End") return total - 1;
  if (key === "ArrowRight") return (currentIndex + 1) % total;
  return (currentIndex - 1 + total) % total;
}

/**
 * @param {string} href
 * @param {string} key
 * @param {string} value
 */
export function setUrlParameter(href, key, value) {
  const url = new URL(href);
  url.searchParams.set(key, value);
  return `${url.pathname}${url.search}${url.hash}`;
}

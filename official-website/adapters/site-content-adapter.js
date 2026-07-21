/**
 * @param {import('../types/site-content.js').SiteContent} content
 */
export function selectMetrics(content) {
  return content.metrics.map((metric) => {
    if (metric.key === "serviceChain") {
      return { ...metric, value: content.serviceChain.length };
    }
    if (metric.key === "transformation") {
      return { ...metric, value: content.transformationStages.length };
    }
    return metric;
  });
}

/**
 * @param {import('../types/site-content.js').SiteContent} content
 * @param {string} moduleId
 */
export function selectBusinessModule(content, moduleId) {
  return content.businessModules.find((item) => item.id === moduleId) || content.businessModules[0] || null;
}

/**
 * @param {unknown} value
 * @param {string} fallback
 */
export function toInternalHref(value, fallback = "#top") {
  return typeof value === "string" && /^#[a-z][\w-]*$/i.test(value) ? value : fallback;
}

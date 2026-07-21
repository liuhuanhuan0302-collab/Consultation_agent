import { siteConfig } from "../config.js";

/** @type {import('../types/site-content.js').SiteContent | null} */
let contentCache = null;

/** @type {Promise<import('../types/site-content.js').SiteContent> | null} */
let pendingRequest = null;

/**
 * @param {unknown} content
 * @returns {import('../types/site-content.js').SiteContent}
 */
function validateContent(content) {
  if (!content || typeof content !== "object") {
    throw new Error("INVALID_CONTENT");
  }

  const candidate = /** @type {Partial<import('../types/site-content.js').SiteContent>} */ (content);
  if (!candidate.company?.name || !candidate.hero?.title || !Array.isArray(candidate.metrics)) {
    throw new Error("MISSING_REQUIRED_CONTENT");
  }

  return /** @type {import('../types/site-content.js').SiteContent} */ (content);
}

/**
 * @param {{url?: string, signal?: AbortSignal, fetchImpl?: typeof fetch}} options
 * @returns {Promise<import('../types/site-content.js').SiteContent>}
 */
export function fetchSiteContent({
  url = siteConfig.contentUrl,
  signal,
  fetchImpl = fetch,
} = {}) {
  return fetchImpl(url, {
    headers: { Accept: "application/json" },
    signal,
  }).then((response) => {
    if (!response.ok) throw new Error("CONTENT_UNAVAILABLE");
    return response.json().then(validateContent);
  });
}

/**
 * @param {{force?: boolean, signal?: AbortSignal}} options
 * @returns {Promise<import('../types/site-content.js').SiteContent>}
 */
export function getSiteContent({ force = false, signal } = {}) {
  if (pendingRequest) return pendingRequest;
  if (!force && contentCache) return Promise.resolve(contentCache);
  if (force) contentCache = null;

  pendingRequest = fetchSiteContent({ signal })
    .then((content) => {
      contentCache = content;
      return content;
    })
    .finally(() => {
      pendingRequest = null;
    });

  return pendingRequest;
}

export function clearSiteContentCache() {
  contentCache = null;
  pendingRequest = null;
}

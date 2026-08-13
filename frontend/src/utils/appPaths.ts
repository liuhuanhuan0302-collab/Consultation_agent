/** 部署路径与当前页面判定 — 由 BASE_URL 和 URL 决定进入公共流程还是后台。 */

export const appBasePath = import.meta.env.BASE_URL.replace(/\/$/, "");
export const appPathname = window.location.pathname.startsWith(appBasePath)
  ? window.location.pathname.slice(appBasePath.length) || "/"
  : window.location.pathname;
export const isAdmin = appPathname.startsWith("/admin");
export const reportToken = appPathname.match(/^\/report\/([^/]+)/)?.[1] || "";

export function appUrl(path: string) {
  return `${appBasePath}${path}` || path;
}

export function sourceFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("source") || "default";
}

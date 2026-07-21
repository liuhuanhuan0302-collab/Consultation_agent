const configuredContentUrl = import.meta.env?.VITE_SITE_CONTENT_URL;

export const DIAGNOSIS_URL = "http://8.138.165.2/?source=ZHIFUBAO";

export const siteConfig = Object.freeze({
  contentUrl: configuredContentUrl || "/data/site-content.json",
});

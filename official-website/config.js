const configuredContentUrl = import.meta.env?.VITE_SITE_CONTENT_URL;
const configuredDiagnosisUrl = import.meta.env?.VITE_DIAGNOSIS_URL;

export const DIAGNOSIS_URL = configuredDiagnosisUrl || "/diagnosis/?source=OFFICIAL_WEBSITE";

export const siteConfig = Object.freeze({
  contentUrl: configuredContentUrl || "/data/site-content.json",
});

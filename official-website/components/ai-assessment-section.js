import { DIAGNOSIS_URL } from "../config.js";

/** @param {ParentNode} root */
function setAssessmentLinks(root) {
  root.querySelectorAll("[data-assessment-link]").forEach((element) => {
    if (element instanceof HTMLAnchorElement) element.href = DIAGNOSIS_URL;
  });
}

/** @param {HTMLElement} root */
export function AssessmentReportCard(root) {
  root.querySelectorAll("[data-score]").forEach((item) => {
    const label = item.querySelector("span")?.textContent?.trim() || "能力项目";
    const score = Number(item.getAttribute("data-score"));
    if (Number.isInteger(score) && score >= 0 && score <= 5) {
      item.setAttribute("aria-label", `${label}：${score} 星，满分 5 星`);
    }
  });
}

/** @param {HTMLElement} root */
export function QRCodeCard(root) {
  setAssessmentLinks(root);
}

/** @param {HTMLElement} root */
export function AiAssessmentSection(root) {
  setAssessmentLinks(root);

  const reportCard = root.querySelector('[data-component="AssessmentReportCard"]');
  if (reportCard instanceof HTMLElement) AssessmentReportCard(reportCard);

  const qrCodeCard = root.querySelector('[data-component="QRCodeCard"]');
  if (qrCodeCard instanceof HTMLElement) QRCodeCard(qrCodeCard);
}

const assessmentSection = document.querySelector('[data-component="AiAssessmentSection"]');
if (assessmentSection instanceof HTMLElement) AiAssessmentSection(assessmentSection);

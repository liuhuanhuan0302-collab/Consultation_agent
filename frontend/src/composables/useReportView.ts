/** 报告展示 — 公开报告页与提交后报告视图共用的展示数据。 */

import { computed, ref, type Ref } from "vue";

import { api } from "../api";
import type { Report, ScoreResponse } from "../types";
import { reportToken } from "../utils/appPaths";
import { normalizeReportHtml, reportHtmlToPlainText, escapeHtmlText } from "../utils/reportHtml";

export function useReportView(score: Ref<ScoreResponse | null>, report: Ref<Report | null>) {
  const publicReport = ref<Report | null>(null);

  const activeReport = computed(() => report.value || publicReport.value);
  const chartDimensions = computed(() => {
    if (score.value?.dimensions?.length) return score.value.dimensions;
    if (publicReport.value?.dimensions?.length) return publicReport.value.dimensions;
    return [];
  });
  const reportTitle = computed(() => activeReport.value?.title || "");
  const reportDate = computed(() => activeReport.value?.created_at || "");
  const reportScore = computed(() => {
    if (score.value) return { total: score.value.total_score, max: score.value.max_score, rate: score.value.score_rate };
    if (publicReport.value?.score) return { total: publicReport.value.score.total, max: publicReport.value.score.max_score, rate: publicReport.value.score.score_rate };
    return null;
  });
  const reportHtml = computed(() => normalizeReportHtml(activeReport.value?.html_content || ""));
  const pdfToken = computed(() => activeReport.value?.public_token || "");
  const currentProblemAnalysis = computed(() => {
    const lowDimensions = activeReport.value?.low_dimensions?.length
      ? activeReport.value.low_dimensions
      : [...chartDimensions.value].sort((a, b) => a.score_rate - b.score_rate).slice(0, 3);
    return lowDimensions.map((item) => ({
      name: item.module_name,
      scoreRate: Math.round(item.score_rate * 100)
    }));
  });
  const reportDemandSummary = computed(() => activeReport.value?.customer_classification?.demand_summary || "");
  const aiProblemAnalysis = computed(() => {
    const content = reportHtmlToPlainText(activeReport.value?.html_content || "");
    if (!content) return "";
    const matched = content.match(/(?:^|\n)#{0,3}\s*AI\s*当前问题分析\s*[:：]?\s*\n?([\s\S]*?)(?=\n#{1,3}\s|\n(?:管理摘要|关键短板|优先 AI 场景|下一步建议)\s*[:：]|$)/i);
    return (matched?.[1] || "").trim().slice(0, 1800);
  });
  const aiProblemAnalysisHtml = computed(() => escapeHtmlText(aiProblemAnalysis.value).replace(/\n/g, "<br>"));

  function updateShareMeta(title: string, description: string, url: string) {
    document.title = title;
    const setMeta = (property: string, content: string) => {
      let el = document.querySelector(`meta[property="${property}"]`) as HTMLMetaElement | null;
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute("property", property);
        document.head.appendChild(el);
      }
      el.setAttribute("content", content);
    };
    setMeta("og:title", title);
    setMeta("og:description", description);
    setMeta("og:url", url);
  }

  async function loadPublicReport() {
    publicReport.value = await api.publicReport(reportToken);
    if (publicReport.value) {
      const summaryScore = publicReport.value.score;
      const desc = summaryScore
        ? `诊断总分 ${summaryScore.total}/${summaryScore.max_score} · 得分率 ${Math.round(summaryScore.score_rate * 100)}%`
        : "查看 AI 原生企业转型诊断报告";
      updateShareMeta(publicReport.value.title, desc, window.location.href);
    }
  }

  return {
    publicReport,
    activeReport,
    chartDimensions,
    reportTitle,
    reportDate,
    reportScore,
    reportHtml,
    pdfToken,
    currentProblemAnalysis,
    reportDemandSummary,
    aiProblemAnalysis,
    aiProblemAnalysisHtml,
    loadPublicReport,
  };
}

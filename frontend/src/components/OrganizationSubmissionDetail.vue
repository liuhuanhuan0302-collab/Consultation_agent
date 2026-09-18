<script setup lang="ts">
import { ref } from "vue";
import { ArrowLeft, ChevronDown, ChevronUp } from "lucide-vue-next";

import type { OrganizationSubmissionAdminDetail } from "../types";
import { formatDateTime } from "../utils/format";

const props = defineProps<{
  detail: OrganizationSubmissionAdminDetail;
  reportGenerating?: boolean;
  reportDownloading?: number | null;
}>();

const emit = defineEmits<{
  close: [];
  generateReport: [];
  downloadReport: [reportId: number];
}>();

const expandedErrorReportId = ref<number | null>(null);

function toggleReportError(reportId: number) {
  expandedErrorReportId.value = expandedErrorReportId.value === reportId ? null : reportId;
}

function reportErrorSummary(text: string) {
  const firstLine = text.trim().split(/\r?\n/)[0] || text;
  return firstLine.length > 90 ? `${firstLine.slice(0, 90)}…` : firstLine;
}

function analysisStatusLabel(status: string) {
  return {
    not_eligible: "暂不生成",
    waiting_manual: "待人工决定",
    queued: "排队中",
    processing: "分析中",
    generated: "已生成",
    failed: "生成失败",
  }[status] || status;
}

function reportStatusLabel(status: string) {
  return { pending: "排队中", generating: "生成中", generated: "已生成", failed: "失败" }[status] || status;
}
</script>

<template>
  <section class="organization-submission-detail table-section" aria-labelledby="organization-submission-detail-title">
    <header class="organization-detail-header">
      <div>
        <p class="eyebrow">原始答卷</p>
        <h2 id="organization-submission-detail-title">{{ detail.respondent_name }}的组织诊断</h2>
      </div>
      <button class="secondary organization-detail-back" type="button" @click="emit('close')"><ArrowLeft :size="16" /> 返回答卷列表</button>
    </header>
    <div class="organization-basic-grid">
      <div><span>企业名称</span><strong>{{ detail.company_name }}</strong></div>
      <div><span>姓名</span><strong>{{ detail.respondent_name }}</strong></div>
      <div><span>部门</span><strong>{{ detail.department }}</strong></div>
      <div><span>职位</span><strong>{{ detail.position }}</strong></div>
      <div><span>状态</span><strong>{{ detail.status === "submitted" ? "已提交" : "草稿" }}</strong></div>
      <div><span>创建时间</span><strong>{{ formatDateTime(detail.created_at) }}</strong></div>
      <div><span>提交时间</span><strong>{{ detail.submitted_at ? formatDateTime(detail.submitted_at) : "-" }}</strong></div>
    </div>
    <section class="organization-analysis-panel" aria-labelledby="organization-analysis-title">
      <div class="organization-analysis-heading">
        <div>
          <p class="eyebrow">固定评分 · 企业信息 · 部门内部AI解读</p>
          <h3 id="organization-analysis-title">组织分析报告</h3>
        </div>
        <button
          v-if="detail.status === 'submitted' && detail.analysis_status !== 'processing' && detail.analysis_status !== 'queued'"
          class="primary"
          type="button"
          :disabled="props.reportGenerating"
          @click="emit('generateReport')"
        >
          {{ props.reportGenerating ? "提交中..." : detail.reports.length ? "人工重新生成" : "生成组织报告" }}
        </button>
      </div>
      <div class="organization-analysis-status">
        <span class="organization-status" :class="detail.analysis_status">{{ analysisStatusLabel(detail.analysis_status) }}</span>
        <span v-if="detail.analysis_note">{{ detail.analysis_note }}</span>
      </div>
      <div v-if="detail.reports.length" class="organization-report-list">
        <div v-for="report in detail.reports" :key="report.id" class="organization-report-row">
          <div><strong>V{{ report.version }}</strong><span>{{ reportStatusLabel(report.status) }}</span></div>
          <small>{{ report.generation_completed_at ? formatDateTime(report.generation_completed_at) : formatDateTime(report.created_at) }}</small>
          <button v-if="report.pdf_available" class="text-action" type="button" :disabled="props.reportDownloading !== null" @click="emit('downloadReport', report.id)">
            {{ props.reportDownloading === report.id ? "下载中..." : "下载PDF" }}
          </button>
          <span v-else-if="!report.generation_error" class="organization-report-error">PDF尚未生成</span>
          <button v-else class="text-action organization-error-toggle" type="button" :aria-expanded="expandedErrorReportId === report.id" @click="toggleReportError(report.id)">
            <span class="organization-error-summary">{{ reportErrorSummary(report.generation_error) }}</span>
            <ChevronDown v-if="expandedErrorReportId !== report.id" :size="15" />
            <ChevronUp v-else :size="15" />
          </button>
          <pre v-if="!report.pdf_available && report.generation_error && expandedErrorReportId === report.id" class="organization-report-error-detail">{{ report.generation_error }}</pre>
        </div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.organization-submission-detail { display: grid; gap: 18px; }
.organization-detail-header { align-items: center; display: flex; gap: 16px; justify-content: space-between; }
.organization-detail-header > div { min-width: 0; }
.organization-detail-header h2 { font-size: 24px; margin: 0; overflow-wrap: anywhere; }
.organization-detail-back { align-items: center; display: inline-flex; flex: 0 0 auto; gap: 6px; white-space: nowrap; }
.organization-analysis-panel { background: linear-gradient(135deg, #f4f8ff, #fbfcff); border: 1px solid #dce6f4; border-radius: 14px; display: grid; gap: 12px; padding: 18px; }
.organization-analysis-heading { align-items: center; display: flex; gap: 16px; justify-content: space-between; }
.organization-analysis-heading h3 { color: #1c3150; font-size: 18px; margin: 2px 0 0; }
.organization-analysis-heading .primary { min-height: 38px; white-space: nowrap; }
.organization-analysis-status { align-items: center; color: #607894; display: flex; flex-wrap: wrap; font-size: 13px; gap: 10px; }
.organization-status.queued, .organization-status.processing { background: #e8f1ff; color: #315fae; }
.organization-status.generated { background: #e8f7ef; color: #167044; }
.organization-status.failed, .organization-status.not_eligible { background: #fff4f2; color: #a3372c; }
.organization-status.waiting_manual { background: #fff4dc; color: #946518; }
.organization-report-list { border-top: 1px solid #e1e8f2; display: grid; gap: 8px; padding-top: 10px; }
.organization-report-row { align-items: center; background: rgba(255, 255, 255, .78); border: 1px solid #e4eaf3; border-radius: 10px; display: grid; gap: 12px; grid-template-columns: 1fr auto minmax(86px, auto); padding: 10px 12px; }
.organization-report-row > div { align-items: center; display: flex; gap: 10px; }
.organization-report-row > div span { color: #607894; font-size: 12px; }
.organization-report-row small { color: #7c8da5; }
.organization-report-error { color: #a3372c; font-size: 12px; text-align: right; }
.organization-error-toggle { align-items: center; color: #a3372c; display: inline-flex; gap: 6px; justify-content: flex-end; max-width: 100%; min-width: 0; }
.organization-error-summary { display: block; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.organization-report-error-detail { background: #fff4f2; border: 1px solid #f5c2bb; border-radius: 8px; color: #a3372c; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; grid-column: 1 / -1; margin: 0; max-height: 240px; overflow: auto; padding: 10px 12px; white-space: pre-wrap; word-break: break-all; }
.organization-basic-grid { display: grid; gap: 10px; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.organization-basic-grid > div:last-child { grid-column: span 2; }
.organization-basic-grid > div { background: #f8fafc; border: 1px solid #e7edf5; border-radius: 10px; display: grid; gap: 4px; min-width: 0; padding: 11px 13px; }
.organization-basic-grid strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 760px) {
  .organization-detail-header { align-items: flex-start; flex-wrap: wrap; }
  .organization-analysis-heading { align-items: flex-start; flex-direction: column; }
  .organization-analysis-heading .primary { width: 100%; }
  .organization-basic-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .organization-report-row { grid-template-columns: 1fr auto; }
  .organization-report-row .organization-report-error { grid-column: 1 / -1; text-align: left; }
  .organization-error-toggle { grid-column: 1 / -1; justify-content: flex-start; }
  .organization-error-summary { max-width: 100%; }
}
@media (max-width: 480px) { .organization-basic-grid { grid-template-columns: 1fr; } }
</style>

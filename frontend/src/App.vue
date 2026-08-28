<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import {
  ArrowLeft,
  ArrowDownToLine,
  BarChart3,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  FileText,
  Lock,
  LogOut,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X
} from "lucide-vue-next";
import CustomerReportView from "./components/CustomerReportView.vue";
import { api } from "./api";
import { dismissToast, error, toasts } from "./composables/feedback";
import { useAdmin, companyResearchSections, researchLegacyText, researchSubsections, searchProviderOfficialUrls } from "./composables/useAdmin";
import { useQuestionnaire } from "./composables/useQuestionnaire";
import { useReportView } from "./composables/useReportView";
import { isAdmin, reportToken } from "./utils/appPaths";
import { bucketPct, completionRate, formatDateTime, pct } from "./utils/format";

const {
  step,
  modules,
  moduleIndex,
  answers,
  score,
  report,
  busy,
  draftSaved,
  reportWaitSeconds,
  reportFailure,
  missingNoticeVisible,
  missingNoticeMessage,
  leadForm,
  phoneWechatSame,
  selectedAiFocus,
  aiFocusOther,
  industries,
  companySizes,
  revenues,
  aiFocusOptions,
  questions,
  answeredCount,
  currentModule,
  progress,
  syncPhoneWechat,
  parseOptionLabels,
  getGlobalIndex,
  bootClient,
  begin,
  submitLead,
  moduleDone,
  isAnswerSelected,
  goToModule,
  goNextModule,
  goPrevModule,
  selectAnswer,
  submitQuestionnaire,
  handleBeforeUnload,
  clearReportPolling,
  restartFlow,
} = useQuestionnaire();

const {
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
} = useReportView(score, report);

const isLocalReportTesting = import.meta.env.DEV && ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname);
const regeneratingReport = ref(false);
let leadStatusRefreshTimer: number | null = null;
let leadStatusRefreshing = false;

const processStatusLabels: Record<string, string> = {
  pending: "未开始",
  queued: "等待处理",
  processing: "处理中",
  generating: "生成中",
  generated: "已完成",
  sent: "已发送",
  failed: "待人工处理",
  review: "待人工审核",
};

function processStatusLabel(status: string | null | undefined) {
  return processStatusLabels[status || ""] || status || "未开始";
}

function processStatusTone(status: string | null | undefined) {
  if (["generated", "sent"].includes(status || "")) return "done";
  if (["failed", "review"].includes(status || "")) return "failed";
  if (["processing", "generating"].includes(status || "")) return "active";
  return "pending";
}

function reportCompanyName(title: string) {
  const company = title.replace(/\s*AI\s*原生转型诊断报告\s*$/, "").trim();
  return company || "企业";
}

function reportShortCompanyName(title: string) {
  const company = reportCompanyName(title);
  return company.replace(/(?:集团股份有限公司|集团有限责任公司|股份有限公司|有限责任公司|集团有限公司|有限公司)$/, "").trim() || company;
}

function reportTitleLengthClass(title: string) {
  const length = Array.from(reportShortCompanyName(title).replace(/\s+/g, "")).length;
  if (length > 16) return "hero-title--extra-long";
  if (length > 10) return "hero-title--long";
  return "";
}

function reportChineseDate(value: string | null | undefined) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未记录";
  const parts = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    timeZone: "Asia/Shanghai",
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value || "";
  return `${part("year")} 年 ${part("month")} 月 ${part("day")} 日`;
}

/** 线索三维跟踪状态的中文映射。 */
const viewStatusLabels: Record<string, string> = {
  unviewed: "尚未查看",
  viewed: "已经查看",
};

const processingStatusLabels: Record<string, string> = {
  pending: "待处理",
  processing: "处理中",
  manual_review: "待人工处理",
  completed: "已完成",
};

const exportStatusLabels: Record<string, string> = {
  unexported: "未导出",
  exported: "已导出",
};

const leadLevelLabels: Record<string, string> = {
  high: "高意向",
  medium: "中意向",
  low: "低意向",
};

function statusLabel(map: Record<string, string>, status: string | null | undefined) {
  return map[status || ""] || status || "-";
}

function formatElapsed(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return "尚未开始";
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分钟`;
}

async function regenerateTestReport() {
  const token = activeReport.value?.public_token;
  if (!token || regeneratingReport.value) return;
  regeneratingReport.value = true;
  error.value = "";
  try {
    const regenerated = await api.regenerateReportForTesting(token);
    if (publicReport.value) publicReport.value = regenerated;
    if (report.value) report.value = regenerated;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "重新生成报告失败";
  } finally {
    regeneratingReport.value = false;
  }
}

const {
  adminToken,
  adminUser,
  adminEmail,
  adminPassword,
  adminTab,
  adminTabs,
  analytics,
  leads,
  leadSortOrder,
  leadCreatedFrom,
  leadCreatedTo,
  leadProcessingFilter,
  leadPage,
  leadAdvancedFilterOpen,
  leadAdvancedFilterDraft,
  leadRuleDialogOpen,
  leadDetailOpen,
  leadDetailLoading,
  selectedLeadDetail,
  researchRunning,
  resumeDeliveryRunning,
  attachmentDeliveryRunning,
  reportRegenerationRunning,
  diagnosticEmailDraft,
  diagnosticEmailUpdating,
  adminQuestions,
  questionBankDialog,
  questionBankSaving,
  cases,
  users,
  channels,
  caseForm,
  userForm,
  channelForm,
  leadsExporting,
  leadsBatchExporting,
  exportBatches,
  exportBatchPanelOpen,
  batchDownloading,
  leadWordExporting,
  questionModuleForm,
  questionForm,
  gatewayConfig,
  reportContactSettings,
  reportContactForm,
  reportContactSaving,
  searchForm,
  llmForm,
  searchSaving,
  searchTesting,
  llmSaving,
  llmTesting,
  searchTestResult,
  llmTestResult,
  canExportLeads,
  canDeleteLeads,
  canManageQuestionBank,
  canManageGateway,
  leadIndustryOptions,
  sourceLabel,
  filteredLeads,
  leadTotalPages,
  pagedLeads,
  leadPageStart,
  leadPageEnd,
  leadPaginationPages,
  leadAdvancedFilterCount,
  leadAdvancedFilterSummary,
  leadDetailReportHtml,
  selectedLeadScoreRate,
  loginAdmin,
  loadAdminShell,
  loadAdminTab,
  goLeadPage,
  syncLeadPageSize,
  openLeadAdvancedFilters,
  closeLeadAdvancedFilters,
  applyLeadAdvancedFilters,
  resetLeadAdvancedFilters,
  openLeadDetail,
  openLeadDetailById,
  closeLeadDetail,
  runLeadResearch,
  resumeReportDelivery,
  retryReportAttachmentDelivery,
  regenerateLeadReport,
  updateLeadDiagnosticEmail,
  exportLeads,
  exportUnexported,
  toggleExportBatches,
  downloadBatch,
  exportLeadWord,
  deleteLead,
  logoutAdmin,
  createCase,
  createChannel,
  createUser,
  deleteChannel,
  openQuestionModuleDialog,
  openQuestionDialog,
  createQuestionModule,
  createQuestion,
  deleteQuestionModule,
  deleteQuestion,
  saveSearchConfig,
  saveLlmConfig,
  testSearchConfig,
  testLlmConfig,
  saveReportContactSettings,
} = useAdmin();

const leadAdvancedFilterTrigger = ref<HTMLButtonElement | null>(null);
const leadAdvancedFilterDialog = ref<HTMLElement | null>(null);

function focusLeadAdvancedFilterDialog() {
  void nextTick(() => {
    leadAdvancedFilterDialog.value
      ?.querySelector<HTMLElement>("select, button, [href], input, [tabindex]:not([tabindex='-1'])")
      ?.focus();
  });
}

function showLeadAdvancedFilters() {
  openLeadAdvancedFilters();
  focusLeadAdvancedFilterDialog();
}

function restoreLeadAdvancedFilterFocus() {
  void nextTick(() => leadAdvancedFilterTrigger.value?.focus());
}

function cancelLeadAdvancedFilters() {
  closeLeadAdvancedFilters();
  restoreLeadAdvancedFilterFocus();
}

function submitLeadAdvancedFilters() {
  applyLeadAdvancedFilters();
  restoreLeadAdvancedFilterFocus();
}

function clearLeadAdvancedFilters() {
  resetLeadAdvancedFilters();
  restoreLeadAdvancedFilterFocus();
}

function handleLeadAdvancedFilterKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    event.preventDefault();
    cancelLeadAdvancedFilters();
    return;
  }
  if (event.key !== "Tab" || !leadAdvancedFilterDialog.value) return;

  const focusable = Array.from(
    leadAdvancedFilterDialog.value.querySelectorAll<HTMLElement>(
      "button:not([disabled]), select:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex='-1'])",
    ),
  ).filter((element) => element.offsetParent !== null);
  if (!focusable.length) return;

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function syncLeadRowsToViewport() {
  syncLeadPageSize(window.innerHeight);
}

onMounted(async () => {
  window.addEventListener("beforeunload", handleBeforeUnload);
  if (isAdmin) {
    syncLeadRowsToViewport();
    window.addEventListener("resize", syncLeadRowsToViewport);
  }
  try {
    if (isAdmin) {
      await loadAdminShell();
    } else if (reportToken) {
      await loadPublicReport();
    } else {
      await bootClient();
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载失败";
  }
  if (isAdmin) {
    leadStatusRefreshTimer = window.setInterval(async () => {
      const detail = selectedLeadDetail.value;
      if (!leadDetailOpen.value || !detail || leadStatusRefreshing) return;
      const statuses = [
        detail.report?.research_status,
        detail.report?.status,
        detail.report?.pdf_status,
        detail.delivery?.status,
      ];
      if (!statuses.some((status) => ["pending", "queued", "processing", "generating"].includes(status || ""))) return;
      leadStatusRefreshing = true;
      try {
        selectedLeadDetail.value = await api.leadDetail(detail.lead.id);
      } finally {
        leadStatusRefreshing = false;
      }
    }, 5000);
  }
});

onBeforeUnmount(() => {
  clearReportPolling();
  window.removeEventListener("beforeunload", handleBeforeUnload);
  window.removeEventListener("resize", syncLeadRowsToViewport);
  if (leadStatusRefreshTimer !== null) window.clearInterval(leadStatusRefreshTimer);
});
</script>

<template>
  <div v-if="missingNoticeVisible" class="top-message" role="status" aria-live="polite">
    <span class="top-message-icon">!</span>
    <span>{{ missingNoticeMessage }}</span>
  </div>

  <div class="toast-stack" role="status" aria-live="polite">
    <div v-for="toast in toasts" :key="toast.id" class="toast" :class="toast.kind">
      <span class="toast-message">{{ toast.message }}</span>
      <div v-if="toast.kind === 'severe'" class="toast-actions">
        <button v-if="toast.leadId" class="toast-link" type="button" @click="dismissToast(toast.id); openLeadDetailById(toast.leadId)">查看客户</button>
        <button class="toast-close" type="button" aria-label="关闭提示" @click="dismissToast(toast.id)">×</button>
      </div>
    </div>
  </div>

  <main v-if="isAdmin && !adminToken" class="login-shell">
    <form class="login-box" @submit.prevent="loginAdmin">
      <Lock :size="28" />
      <h1>后台登录</h1>
      <label>邮箱<input v-model="adminEmail" /></label>
      <label>密码<input v-model="adminPassword" type="password" /></label>
      <button class="primary">登录</button>
    </form>
  </main>

  <main v-else-if="isAdmin" class="admin-shell">
    <aside class="admin-sidebar">
      <div>
        <p class="eyebrow">后台</p>
        <h1>咨询诊断 Agent</h1>
      </div>
      <div class="admin-user"><ShieldCheck :size="18" /> {{ adminUser?.name || "管理员" }}</div>
      <nav class="admin-nav" aria-label="后台功能导航">
        <button v-for="tab in adminTabs" :key="tab.key" :class="{ active: adminTab === tab.key }" @click="loadAdminTab(tab.key)">
          <component :is="tab.icon" :size="18" /> <span>{{ tab.label }}</span>
        </button>
      </nav>
      <button class="secondary admin-logout" @click="logoutAdmin"><LogOut :size="18" /> 退出</button>
    </aside>
    <section class="admin-main">

      <div v-if="adminTab === 'overview'">
        <div v-if="analytics" class="metric-grid">
          <div class="metric"><BarChart3 :size="18" /><span>访问 UV</span><strong>{{ analytics.visit_uv }}</strong></div>
          <div class="metric"><BarChart3 :size="18" /><span>开始自测</span><strong>{{ analytics.started_count }}</strong></div>
          <div class="metric"><BarChart3 :size="18" /><span>信息完成</span><strong>{{ analytics.info_completed_count }}</strong></div>
          <div class="metric"><BarChart3 :size="18" /><span>问卷完成</span><strong>{{ analytics.questionnaire_completed_count }}</strong></div>
          <div class="metric"><BarChart3 :size="18" /><span>报告生成</span><strong>{{ analytics.report_generated_count }}</strong></div>
          <div class="metric"><BarChart3 :size="18" /><span>报告领取</span><strong>{{ analytics.report_claimed_count }}</strong></div>
          <div class="metric"><BarChart3 :size="18" /><span>高意向线索</span><strong>{{ analytics.high_intent_leads }}</strong></div>
          <div class="metric"><BarChart3 :size="18" /><span>线索总数</span><strong>{{ analytics.lead_count }}</strong></div>
        </div>
        <div v-if="analytics" class="analytics-panel-grid">
          <section class="analytics-card funnel-card">
            <header>
              <h2>答题完成率</h2>
              <strong>{{ completionRate(analytics.questionnaire_completion_rate) }}</strong>
            </header>
            <div class="funnel-list">
              <div v-for="item in analytics.funnel" :key="item.label" class="funnel-row">
                <span>{{ item.label }}</span>
                <div class="funnel-track"><i :style="{ width: `${Math.round(item.rate * 100)}%` }"></i></div>
                <b>{{ item.count }}</b>
                <em>{{ pct(item.rate) }}</em>
              </div>
            </div>
          </section>

          <section class="analytics-card hourly-card">
            <header>
              <h2>答题时间段人数</h2>
              <span>按问卷完成时间统计</span>
            </header>
            <div class="hour-bars">
              <div v-for="item in analytics.hourly_questionnaire_counts" :key="item.label" class="hour-bar" :title="`${item.label} · ${item.count}人`">
                <i :style="{ height: bucketPct(item.count, analytics.hourly_questionnaire_counts) }"></i>
                <span>{{ item.label.slice(0, 2) }}</span>
              </div>
            </div>
          </section>

          <section class="analytics-card distribution-card">
            <header><h2>线索等级分布</h2></header>
            <div class="rank-list">
              <div v-for="item in analytics.lead_level_distribution" :key="item.label">
                <span>{{ item.label }}</span>
                <div><i :style="{ width: bucketPct(item.count, analytics.lead_level_distribution) }"></i></div>
                <b>{{ item.count }}</b>
              </div>
            </div>
          </section>

          <section class="analytics-card distribution-card industry-card">
            <header><h2>行业分布</h2></header>
            <div class="rank-list">
              <div v-for="item in analytics.industry_distribution" :key="item.label">
                <span>{{ item.label }}</span>
                <div><i :style="{ width: bucketPct(item.count, analytics.industry_distribution) }"></i></div>
                <b>{{ item.count }}</b>
              </div>
            </div>
          </section>
        </div>
        <div v-else class="loading">加载中...</div>
      </div>

      <template v-if="adminTab === 'leads'">
      <section v-if="!leadDetailOpen" class="table-section">
        <div class="table-actions">
          <h2>线索列表</h2>
          <div class="table-action-buttons">
            <button class="secondary" type="button" @click="leadRuleDialogOpen = true"><BookOpen :size="18" /> 评分规则</button>
            <button v-if="canExportLeads" class="secondary" type="button" :disabled="leadsExporting" @click="exportLeads"><ArrowDownToLine :size="18" /> {{ leadsExporting ? "导出中..." : "导出筛选结果" }}</button>
            <button v-if="canExportLeads" class="primary" type="button" :disabled="leadsBatchExporting" @click="exportUnexported"><ArrowDownToLine :size="18" /> {{ leadsBatchExporting ? "导出中..." : "一键导出未导出客户" }}</button>
            <button v-if="canExportLeads" class="secondary" type="button" @click="toggleExportBatches"><FileText :size="18" /> {{ exportBatchPanelOpen ? "收起导出历史" : "导出历史" }}</button>
          </div>
        </div>
        <div class="lead-toolbar lead-toolbar-quick">
          <label class="lead-filter-date">
            创建日期
            <span class="date-range">
              <input v-model="leadCreatedFrom" type="date" aria-label="创建日期起" />
              <span class="date-sep">至</span>
              <input v-model="leadCreatedTo" type="date" aria-label="创建日期止" />
            </span>
          </label>
          <label>
            处理状态
            <select v-model="leadProcessingFilter">
              <option value="">全部</option>
              <option value="pending">待处理</option>
              <option value="processing">处理中</option>
              <option value="manual_review">待人工处理</option>
              <option value="completed">已完成</option>
            </select>
          </label>
          <label>
            时间排序
            <select v-model="leadSortOrder">
              <option value="newest">最新优先</option>
              <option value="oldest">最早优先</option>
            </select>
          </label>
          <button
            ref="leadAdvancedFilterTrigger"
            class="secondary lead-more-filter"
            type="button"
            aria-haspopup="dialog"
            :aria-expanded="leadAdvancedFilterOpen"
            @click="showLeadAdvancedFilters"
          >
            <SlidersHorizontal :size="17" />
            更多筛选
            <span v-if="leadAdvancedFilterCount" class="filter-count" aria-label="已启用高级筛选数量">{{ leadAdvancedFilterCount }}</span>
          </button>
          <div class="lead-count">共 {{ filteredLeads.length }} 条</div>
          <div v-if="leadAdvancedFilterSummary.length" class="lead-filter-summary" aria-live="polite">
            <span class="lead-filter-summary-label">已启用：</span>
            <span v-for="item in leadAdvancedFilterSummary" :key="item" class="filter-chip">{{ item }}</span>
          </div>
        </div>
        <div class="leads-table-wrap">
          <table class="leads-table">
            <thead><tr><th>公司</th><th>行业</th><th>联系人</th><th>职位</th><th>联系</th><th>等级</th><th>查看</th><th>处理</th><th>导出</th><th>最近处理时间</th><th v-if="canDeleteLeads">操作</th></tr></thead>
            <tbody>
              <tr v-for="lead in pagedLeads" :key="lead.id" class="clickable-row" tabindex="0" @click="openLeadDetail(lead)" @keydown.enter="openLeadDetail(lead)">
                <td :title="lead.company_name || ''">{{ lead.company_name }}</td>
                <td :title="lead.industry || ''">{{ lead.industry }}</td>
                <td :title="lead.contact_name || ''">{{ lead.contact_name }}</td>
                <td :title="lead.position || ''">{{ lead.position }}</td>
                <td :title="lead.phone || lead.wechat || ''">{{ lead.phone || lead.wechat }}</td>
                <td><span class="pill" :class="lead.lead_level">{{ statusLabel(leadLevelLabels, lead.lead_level) }}</span></td>
                <td>{{ statusLabel(viewStatusLabels, lead.view_status) }}</td>
                <td>
                  <span class="status-badge" :class="`status-${lead.processing_status}`" :title="lead.processing_note || ''">
                    {{ statusLabel(processingStatusLabels, lead.processing_status) }}
                  </span>
                </td>
                <td>{{ statusLabel(exportStatusLabels, lead.export_status) }}</td>
                <td>{{ formatDateTime(lead.last_activity_at || lead.updated_at || lead.created_at) }}</td>
                <td v-if="canDeleteLeads" class="lead-row-actions">
                  <button class="icon-button danger-icon-button" type="button" :title="`删除线索：${lead.company_name || lead.id}`" @click.stop="deleteLead(lead)"><Trash2 :size="16" /></button>
                </td>
              </tr>
              <tr v-if="!pagedLeads.length">
                <td :colspan="canDeleteLeads ? 11 : 10" class="empty-cell">暂无符合条件的线索</td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="pagination">
          <span>显示 {{ leadPageStart }}-{{ leadPageEnd }} / {{ filteredLeads.length }}</span>
          <nav class="pagination-nav" aria-label="线索列表分页">
            <button class="secondary pagination-edge" type="button" :disabled="leadPage <= 1" aria-label="第一页" title="第一页" @click="goLeadPage(1)">
              <ChevronsLeft :size="16" /><span class="pagination-label">首页</span>
            </button>
            <button class="secondary pagination-edge" type="button" :disabled="leadPage <= 1" aria-label="上一页" @click="goLeadPage(leadPage - 1)">
              <ChevronLeft :size="16" /><span class="pagination-label">上一页</span>
            </button>
            <div class="pagination-pages">
              <template v-for="item in leadPaginationPages" :key="item">
                <button
                  v-if="typeof item === 'number'"
                  class="pagination-page"
                  :class="{ active: item === leadPage }"
                  type="button"
                  :aria-current="item === leadPage ? 'page' : undefined"
                  :aria-label="`第 ${item} 页`"
                  @click="goLeadPage(item)"
                >{{ item }}</button>
                <span v-else class="pagination-ellipsis" aria-hidden="true">…</span>
              </template>
            </div>
            <button class="secondary pagination-edge" type="button" :disabled="leadTotalPages === 0 || leadPage >= leadTotalPages" aria-label="下一页" @click="goLeadPage(leadPage + 1)">
              <span class="pagination-label">下一页</span><ChevronRight :size="16" />
            </button>
            <button class="secondary pagination-edge" type="button" :disabled="leadTotalPages === 0 || leadPage >= leadTotalPages" aria-label="最后一页" title="最后一页" @click="goLeadPage(leadTotalPages)">
              <span class="pagination-label">尾页</span><ChevronsRight :size="16" />
            </button>
          </nav>
        </footer>

        <section v-if="exportBatchPanelOpen" class="export-batches-panel">
          <header>
            <h3>导出历史</h3>
            <span>每次「一键导出未导出客户」成功后自动保存批次，可随时按历史批次重新下载。</span>
          </header>
          <div class="leads-table-wrap">
            <table class="leads-table export-batches-table">
              <thead><tr><th>批次</th><th>导出时间</th><th>客户数</th><th>操作人</th><th>说明</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="batch in exportBatches" :key="batch.id">
                  <td>#{{ batch.id }}</td>
                  <td>{{ formatDateTime(batch.created_at) }}</td>
                  <td>{{ batch.rows_count }}</td>
                  <td>{{ batch.exported_by || "-" }}</td>
                  <td :title="batch.file_name || ''">{{ batch.filters_summary || "-" }}</td>
                  <td>
                    <button class="secondary compact-button" type="button" :disabled="batchDownloading !== null" @click="downloadBatch(batch)">
                      {{ batchDownloading === batch.id ? "下载中..." : "重新下载" }}
                    </button>
                  </td>
                </tr>
                <tr v-if="!exportBatches.length">
                  <td colspan="6" class="empty-cell">暂无导出批次</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section v-else class="table-section lead-detail-page" aria-labelledby="lead-detail-title">
        <header class="lead-detail-page-header">
          <div>
            <p class="eyebrow">客户详情</p>
            <h2 id="lead-detail-title">{{ selectedLeadDetail?.lead.company_name || "客户详情" }}</h2>
          </div>
          <div class="lead-detail-actions">
            <button
              v-if="selectedLeadDetail && canDeleteLeads"
              class="danger-text-button"
              type="button"
              @click="deleteLead(selectedLeadDetail.lead)"
            ><Trash2 :size="16" /> 删除该线索</button>
            <button
              v-if="selectedLeadDetail && canExportLeads"
              class="primary"
              type="button"
              :disabled="leadWordExporting"
              @click="exportLeadWord"
            ><ArrowDownToLine :size="17" /> {{ leadWordExporting ? "导出中..." : "导出 Word" }}</button>
            <button class="secondary" type="button" @click="closeLeadDetail"><ArrowLeft :size="17" /> 返回线索列表</button>
          </div>
        </header>

        <div v-if="leadDetailLoading" class="loading">客户详情加载中...</div>
        <div v-else-if="selectedLeadDetail" class="lead-detail-body">
          <section class="detail-block">
            <h3>处理进度</h3>
            <div class="process-status-grid">
              <article :class="processStatusTone(selectedLeadDetail.report?.research_status)">
                <span>企业情报</span>
                <strong>{{ processStatusLabel(selectedLeadDetail.report?.research_status) }}</strong>
                <small>耗时 {{ formatElapsed(selectedLeadDetail.report?.research_elapsed_seconds) }}</small>
              </article>
              <article :class="processStatusTone(selectedLeadDetail.report?.status)">
                <span>AI 报告</span>
                <strong>{{ processStatusLabel(selectedLeadDetail.report?.status) }}</strong>
                <small>耗时 {{ formatElapsed(selectedLeadDetail.report?.generation_elapsed_seconds) }}</small>
              </article>
              <article :class="processStatusTone(selectedLeadDetail.report?.pdf_status)">
                <span>报告文件</span>
                <strong>{{ processStatusLabel(selectedLeadDetail.report?.pdf_status) }}</strong>
                <small>耗时 {{ formatElapsed(selectedLeadDetail.report?.pdf_elapsed_seconds) }}</small>
              </article>
              <article :class="processStatusTone(selectedLeadDetail.delivery?.status)">
                <span>邮件发送</span>
                <strong>{{ processStatusLabel(selectedLeadDetail.delivery?.status) }}</strong>
                <small>耗时 {{ formatElapsed(selectedLeadDetail.delivery?.elapsed_seconds) }}</small>
                <small v-if="selectedLeadDetail.delivery?.queue_position">队列第 {{ selectedLeadDetail.delivery.queue_position }} 位</small>
              </article>
            </div>
          </section>
          <section class="detail-block">
            <h3>基本信息</h3>
            <div class="detail-grid">
              <div><span>公司</span><strong>{{ selectedLeadDetail.lead.company_name || "-" }}</strong></div>
              <div><span>所在城市</span><strong>{{ selectedLeadDetail.lead.city || "-" }}</strong></div>
              <div><span>行业</span><strong>{{ selectedLeadDetail.lead.industry || "-" }}</strong></div>
              <div><span>规模</span><strong>{{ selectedLeadDetail.lead.company_size || "-" }}</strong></div>
              <div><span>年营收</span><strong>{{ selectedLeadDetail.lead.annual_revenue || "-" }}</strong></div>
              <div><span>联系人</span><strong>{{ selectedLeadDetail.lead.contact_name || "-" }}</strong></div>
              <div><span>职位</span><strong>{{ selectedLeadDetail.lead.position || "-" }}</strong></div>
              <div><span>手机号</span><strong>{{ selectedLeadDetail.lead.phone || "-" }}</strong></div>
              <div><span>邮箱</span><strong>{{ selectedLeadDetail.lead.email || "-" }}</strong></div>
              <div><span>微信</span><strong>{{ selectedLeadDetail.lead.wechat || "-" }}</strong></div>
              <div><span>来源</span><strong :title="selectedLeadDetail.lead.source_code || ''">{{ sourceLabel(selectedLeadDetail.lead.source_code) }}</strong></div>
              <div><span>首次查看</span><strong>{{ selectedLeadDetail.lead.first_viewed_at ? formatDateTime(selectedLeadDetail.lead.first_viewed_at) : "-" }}</strong></div>
              <div><span>首次查看人</span><strong>{{ selectedLeadDetail.lead.first_viewed_by || "-" }}</strong></div>
              <div><span>首次导出</span><strong>{{ selectedLeadDetail.lead.first_exported_at ? formatDateTime(selectedLeadDetail.lead.first_exported_at) : "-" }}</strong></div>
              <div><span>最近导出</span><strong>{{ selectedLeadDetail.lead.last_exported_at ? formatDateTime(selectedLeadDetail.lead.last_exported_at) : "-" }}</strong></div>
            </div>
            <div v-if="adminUser?.role === 'admin'" class="diagnostic-email-editor">
              <div>
                <span>诊断邮箱投递</span>
                <p v-if="selectedLeadDetail.delivery?.status === 'failed'">最近发送失败：{{ selectedLeadDetail.delivery.last_error || "未知原因" }}</p>
                <p v-else-if="selectedLeadDetail.delivery?.status === 'sent'">已发送至 {{ selectedLeadDetail.delivery.recipient_email }}{{ selectedLeadDetail.delivery.sent_at ? ` · ${formatDateTime(selectedLeadDetail.delivery.sent_at)}` : "" }}</p>
                <p v-else-if="selectedLeadDetail.delivery">当前状态：{{ selectedLeadDetail.delivery.status === 'processing' ? "发送中" : "等待发送" }} · {{ selectedLeadDetail.delivery.recipient_email }}</p>
                <p v-else>尚未创建报告投递任务。</p>
              </div>
              <div v-if="canExportLeads" class="diagnostic-email-edit-row">
                <input v-model="diagnosticEmailDraft" type="email" placeholder="更正后的诊断邮箱" />
                <button class="primary" type="button" :disabled="diagnosticEmailUpdating" @click="updateLeadDiagnosticEmail">
                  {{ diagnosticEmailUpdating ? "处理中..." : "更正并补发" }}
                </button>
              </div>
            </div>
            <div class="detail-demand">
              <span>AI 转型关注点</span>
              <p>{{ selectedLeadDetail.lead.ai_focus || selectedLeadDetail.lead.demand_summary || "未填写" }}</p>
            </div>
          </section>

          <section class="detail-block">
            <h3>诊断结果</h3>
            <div class="detail-score-grid">
              <div><span>线索等级</span><strong><span class="pill" :class="selectedLeadDetail.lead.lead_level">{{ statusLabel(leadLevelLabels, selectedLeadDetail.lead.lead_level) }}</span></strong></div>
              <div><span>总分</span><strong>{{ selectedLeadDetail.submission?.total_score ?? "-" }}/{{ selectedLeadDetail.submission?.max_score ?? "-" }}</strong></div>
              <div><span>得分率</span><strong>{{ selectedLeadScoreRate }}</strong></div>
              <div><span>提交时间</span><strong>{{ selectedLeadDetail.submission?.submitted_at ? formatDateTime(selectedLeadDetail.submission.submitted_at) : "-" }}</strong></div>
            </div>
            <div v-if="selectedLeadDetail.submission?.dimensions?.length" class="dimension-mini-list">
              <div v-for="item in selectedLeadDetail.submission.dimensions" :key="item.module_code">
                <span>{{ item.module_name }}</span>
                <b>{{ Math.round(item.score_rate * 100) }}%</b>
              </div>
            </div>
          </section>

          <section class="detail-block">
            <h3>企业情报与 AI 分析</h3>
            <div v-if="selectedLeadDetail.report?.company_research" class="company-research-view">
              <div class="company-research-sections">
                <div v-for="[key, label] in companyResearchSections" :key="key" class="company-research-item">
                  <span>{{ label }}</span>
                  <div v-if="researchSubsections(selectedLeadDetail.report.company_research[key]).length" class="company-research-subsections">
                    <div v-for="item in researchSubsections(selectedLeadDetail.report.company_research[key])" :key="item.title" class="company-research-subsection">
                      <strong>{{ item.title }}</strong>
                      <p>{{ item.content }}</p>
                    </div>
                  </div>
                  <p v-else>{{ researchLegacyText(selectedLeadDetail.report.company_research[key]) || "公开渠道未披露" }}</p>
                </div>
              </div>
              <div class="detail-demand">
                <span>AI 综合分析</span>
                <div v-if="researchSubsections(selectedLeadDetail.report.company_research.analysis).length" class="company-research-subsections">
                  <div v-for="item in researchSubsections(selectedLeadDetail.report.company_research.analysis)" :key="item.title" class="company-research-subsection">
                    <strong>{{ item.title }}</strong>
                    <p>{{ item.content }}</p>
                  </div>
                </div>
                <p v-else>{{ researchLegacyText(selectedLeadDetail.report.company_research.analysis) || "暂无" }}</p>
              </div>
              <div v-if="selectedLeadDetail.report.company_research.sources?.length" class="company-research-sources">
                <span>信息来源</span>
                <ul>
                  <li v-for="(source, index) in selectedLeadDetail.report.company_research.sources" :key="index">
                    <a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title || source.url }}</a>
                  </li>
                </ul>
              </div>
            </div>
            <p v-else class="empty-detail">尚未生成企业情报，请查看当前检索状态或等待系统自动重试。</p>
            <div v-if="selectedLeadDetail.report?.generation_error" class="generation-error-banner">
              <strong>生成提示：</strong>{{ selectedLeadDetail.report.generation_error }}
            </div>
            <div v-if="adminUser?.role === 'admin'" class="research-trigger">
              <button class="secondary" type="button" :disabled="researchRunning" @click="runLeadResearch">
                {{ researchRunning ? "正在联网检索企业信息…" : selectedLeadDetail.report?.company_research ? "重新检索企业信息" : "手动搜索企业信息" }}
              </button>
              <button
                v-if="selectedLeadDetail.report?.research_status === 'generated' && (selectedLeadDetail.report?.status === 'failed' || !selectedLeadDetail.delivery)"
                class="primary"
                type="button"
                :disabled="resumeDeliveryRunning"
                @click="resumeReportDelivery"
              >
                {{ resumeDeliveryRunning ? "正在重新入队…" : "继续生成报告并发送" }}
              </button>
              <button
                v-if="selectedLeadDetail.report?.html_content && ['generated', 'fallback'].includes(selectedLeadDetail.report.status) && selectedLeadDetail.delivery?.status === 'failed'"
                class="primary"
                type="button"
                :disabled="attachmentDeliveryRunning"
                @click="retryReportAttachmentDelivery"
              >
                {{ attachmentDeliveryRunning ? "正在重新生成附件…" : "重新生成附件并发送" }}
              </button>
            </div>
          </section>

          <section class="detail-block">
            <div class="detail-block-heading">
              <h3>AI 分析报告</h3>
              <button
                v-if="adminUser?.role === 'admin' && selectedLeadDetail.report?.html_content"
                class="secondary compact-button"
                type="button"
                :disabled="reportRegenerationRunning || selectedLeadDetail.report?.status === 'generating'"
                @click="regenerateLeadReport"
              >
                <Sparkles :size="16" />
                {{ reportRegenerationRunning || selectedLeadDetail.report?.status === "generating" ? "正在重新生成…" : "重新生成 AI 报告" }}
              </button>
            </div>
            <CustomerReportView
              v-if="selectedLeadDetail.report?.html_content"
              admin-preview
              :company-name="selectedLeadDetail.lead.company_name || '企业'"
              :report-id="selectedLeadDetail.report.id"
              :created-at="selectedLeadDetail.report.created_at"
              :score="selectedLeadDetail.submission?.total_score != null && selectedLeadDetail.submission?.score_rate != null ? {
                total: selectedLeadDetail.submission.total_score,
                max: selectedLeadDetail.submission.max_score,
                rate: selectedLeadDetail.submission.score_rate,
              } : null"
              :dimensions="selectedLeadDetail.submission?.dimensions || []"
              :html="leadDetailReportHtml"
            />
            <p v-else class="empty-detail">报告还未生成或暂无内容。</p>
          </section>
        </div>
      </section>
      </template>

      <div v-if="adminTab === 'questions'" class="module-list">
        <header class="question-bank-header">
          <div>
            <p class="eyebrow">题库管理</p>
            <h2>诊断题库</h2>
          </div>
          <button v-if="canManageQuestionBank" class="primary" type="button" @click="openQuestionModuleDialog"><Plus :size="18" /> 新增题库</button>
        </header>
        <section v-for="module in adminQuestions" :key="module.id" class="module-block">
          <header class="module-block-header">
            <h2>{{ module.sort_order }}. {{ module.name }}<span>{{ module.max_score }}分</span></h2>
            <div v-if="canManageQuestionBank" class="module-actions">
              <button class="secondary compact-button" type="button" @click="openQuestionDialog(module)"><Plus :size="16" /> 新增题目</button>
              <button class="icon-button danger-icon-button" type="button" :title="`删除题库：${module.name}`" @click="deleteQuestionModule(module)"><Trash2 :size="17" /></button>
            </div>
          </header>
          <div v-for="question in module.questions" :key="question.id" class="question-bank-row">
            <p>{{ question.code }} · {{ question.text }}</p>
            <button v-if="canManageQuestionBank" class="icon-button danger-icon-button" type="button" :title="`删除题目：${question.code}`" @click="deleteQuestion(question)"><Trash2 :size="16" /></button>
          </div>
        </section>
      </div>

      <div v-if="adminTab === 'gateway'" class="gateway-panel">
        <header class="question-bank-header">
          <div>
            <p class="eyebrow">系统配置</p>
            <h2>API 网关配置</h2>
          </div>
        </header>
        <div v-if="gatewayConfig?.key_reentry_required" class="gateway-key-warning">检测到加密密钥已轮换，已保存的 API Key 无法解密，请重新填写搜索 / LLM Key 并保存。</div>

        <section class="module-block gateway-card">
          <header class="module-block-header">
            <h2>搜索配置<span>公司情报检索</span></h2>
          </header>
          <p class="gateway-hint">客户提交问卷后，系统会自动检索目标公司的公开信息并生成企业情报与 AI 分析。DeepSeek 联网搜索默认共用服务器 .env 中的 API Key；如在此单独填写 Key，则优先使用后台配置。API Key 以掩码显示，输入框留空表示保留原值。</p>
          <div class="question-bank-number-grid">
            <label>搜索服务商
              <select v-model="searchForm.search_provider">
                <option value="bocha">博查 Bocha</option>
                <option value="serpapi">SerpAPI</option>
                <option value="deepseek">DeepSeek 联网搜索</option>
                <option value="custom">自定义</option>
              </select>
            </label>
            <label v-if="searchForm.search_provider === 'custom'">接口地址<input v-model="searchForm.search_base_url" placeholder="https:// 公网地址（必填）" /></label>
            <p v-else class="gateway-hint gateway-official-url">接口地址：{{ searchProviderOfficialUrls[searchForm.search_provider] }}（官方固定，不可修改）</p>
          </div>
          <label v-if="searchForm.search_provider === 'deepseek'">检索模型<input v-model="searchForm.search_model" placeholder="留空使用默认 deepseek-v4-flash" /></label>
          <label>搜索 API Key<input v-model="searchForm.search_api_key" type="password" :placeholder="gatewayConfig?.search_api_key ? `当前：${gatewayConfig.search_api_key}` : searchForm.search_provider === 'deepseek' ? '使用服务器 DEEPSEEK_API_KEY' : '请输入 API Key'" /></label>
          <div class="question-bank-number-grid">
            <label>超时（秒）<input v-model.number="searchForm.search_timeout_seconds" type="number" min="3" max="120" /></label>
            <label>最大结果数<input v-model.number="searchForm.search_max_results" type="number" min="1" max="50" /></label>
          </div>
          <div class="gateway-actions">
            <button class="secondary" type="button" :disabled="searchTesting" @click="testSearchConfig">{{ searchTesting ? "测试中..." : "测试搜索接口" }}</button>
            <button class="primary" type="button" :disabled="searchSaving || !canManageGateway" @click="saveSearchConfig">{{ searchSaving ? "保存中..." : "保存搜索配置" }}</button>
          </div>
          <p v-if="searchTestResult" class="gateway-test-result" :class="searchTestResult.ok ? 'gateway-test-ok' : 'gateway-test-fail'">{{ searchTestResult.text }}</p>
        </section>

        <section class="module-block gateway-card">
          <header class="module-block-header">
            <h2>大模型配置<span>可选</span></h2>
          </header>
          <p class="gateway-hint">用于报告生成与公司情报分析的大模型。全部留空则使用服务器 .env 中的 DeepSeek 配置。接口地址仅支持 DeepSeek 官方域名（https://api.deepseek.com）或通过安全校验的公网 https 服务，且更换地址时必须同时填写新的 LLM Key（系统会自动拼接 /v1/chat/completions）。</p>
          <label>接口地址<input v-model="llmForm.llm_base_url" placeholder="如 https://api.deepseek.com" /></label>
          <div class="question-bank-number-grid">
            <label>LLM API Key<input v-model="llmForm.llm_api_key" type="password" :placeholder="gatewayConfig?.llm_api_key ? `当前：${gatewayConfig.llm_api_key}` : '留空使用 .env'" /></label>
            <label>模型名称<input v-model="llmForm.llm_model" placeholder="如 deepseek-chat" /></label>
          </div>
          <div class="gateway-actions">
            <button class="secondary" type="button" :disabled="llmTesting" @click="testLlmConfig">{{ llmTesting ? "测试中..." : "测试大模型" }}</button>
            <button class="primary" type="button" :disabled="llmSaving || !canManageGateway" @click="saveLlmConfig">{{ llmSaving ? "保存中..." : "保存大模型配置" }}</button>
          </div>
          <p v-if="llmTestResult" class="gateway-test-result" :class="llmTestResult.ok ? 'gateway-test-ok' : 'gateway-test-fail'">{{ llmTestResult.text }}</p>
        </section>
      </div>

      <section v-if="adminTab === 'settings'" class="system-settings-panel">
        <form class="module-block system-settings-form" @submit.prevent="saveReportContactSettings">
          <header>
            <div>
              <p class="eyebrow">报告联系信息</p>
              <h2>进一步沟通</h2>
            </div>
            <button class="primary" type="submit" :disabled="reportContactSaving">
              <Check :size="18" /> {{ reportContactSaving ? "保存中..." : "保存设置" }}
            </button>
          </header>
          <p class="gateway-hint">仅影响新生成或重新生成的报告；已生成报告保持原内容。全部留空时，报告不显示“进一步沟通”。</p>
          <div class="system-settings-grid">
            <label>联系人<input v-model="reportContactForm.contact_name" maxlength="120" placeholder="例如：优小越" /></label>
            <label>电话<input v-model="reportContactForm.phone" maxlength="64" placeholder="请输入联系电话" /></label>
            <label>微信号<input v-model="reportContactForm.wechat" maxlength="120" placeholder="请输入微信号" /></label>
            <label>邮箱<input v-model="reportContactForm.email" maxlength="254" type="email" placeholder="请输入邮箱" /></label>
          </div>
          <small v-if="reportContactSettings?.updated_at" class="settings-updated-at">最近更新：{{ formatDateTime(reportContactSettings.updated_at) }}<span v-if="reportContactSettings.updated_by"> · {{ reportContactSettings.updated_by }}</span></small>
        </form>
      </section>

      <section v-if="adminTab === 'cases'" class="case-layout">
        <form class="case-form" @submit.prevent="createCase">
          <h2>新增案例</h2>
          <input v-model="caseForm.title" required placeholder="案例标题" />
          <input v-model="caseForm.industry" placeholder="行业" />
          <input v-model="caseForm.function_area" required placeholder="职能方向" />
          <select v-model="caseForm.module_code">
            <option v-for="n in 10" :key="n">M{{ String(n).padStart(2, "0") }}</option>
          </select>
          <textarea v-model="caseForm.description" required placeholder="案例描述" />
          <textarea v-model="caseForm.expected_benefit" required placeholder="预期收益" />
          <button class="primary"><Plus :size="18" /> 添加</button>
        </form>
        <div class="case-list">
          <article v-for="item in cases" :key="item.id" class="case-item">
            <h3>{{ item.title }}</h3>
            <p>{{ item.industry }} · {{ item.function_area }} · {{ item.priority_tag }}</p>
            <p>{{ item.description }}</p>
          </article>
        </div>
      </section>

      <section v-if="adminTab === 'channels'" class="case-layout">
        <form class="case-form" @submit.prevent="createChannel">
          <h2>新增渠道</h2>
          <input v-model="channelForm.code" required placeholder="渠道编码（如 wechat_mp）" />
          <input v-model="channelForm.name" required placeholder="渠道名称（如 微信公众号）" />
          <input v-model="channelForm.description" placeholder="描述" />
          <button class="primary"><Plus :size="18" /> 添加</button>
        </form>
        <div class="channel-list">
          <article v-for="item in channels" :key="item.id" class="channel-item">
            <div class="channel-qr">
              <img :src="`/api/public/channels/${item.code}/qr`" :alt="item.name" />
            </div>
            <div class="channel-info">
              <h3>{{ item.name }}</h3>
              <p>{{ item.code }}<span v-if="item.description"> · {{ item.description }}</span></p>
              <button class="danger-text-button" @click="deleteChannel(item)"><Trash2 :size="15" /> 删除二维码</button>
            </div>
          </article>
        </div>
      </section>

      <section v-if="adminTab === 'users'" class="user-layout">
        <form class="case-form" @submit.prevent="createUser">
          <h2>新增账号</h2>
          <input v-model="userForm.email" required placeholder="邮箱" />
          <input v-model="userForm.name" required placeholder="姓名" />
          <select v-model="userForm.role">
            <option value="operator">运营</option>
            <option value="sales">销售</option>
            <option value="consultant">顾问/FDE</option>
            <option value="admin">管理员</option>
          </select>
          <input v-model="userForm.password" type="password" required minlength="8" autocomplete="new-password" placeholder="初始密码（不少于 8 位）" />
          <button class="primary"><Check :size="18" /> 创建</button>
        </form>
        <div class="table-section">
          <table>
            <thead><tr><th>姓名</th><th>邮箱</th><th>角色</th><th>状态</th></tr></thead>
            <tbody><tr v-for="item in users" :key="item.id"><td>{{ item.name }}</td><td>{{ item.email }}</td><td>{{ item.role }}</td><td>{{ item.is_active ? "启用" : "停用" }}</td></tr></tbody>
          </table>
        </div>
      </section>
    </section>
  </main>

  <main v-else-if="reportToken" class="report-shell">
    <div v-if="error" class="alert">{{ error }}</div>
    <CustomerReportView
      v-if="publicReport"
      :company-name="reportCompanyName(reportTitle)"
      :report-id="publicReport.id"
      :created-at="publicReport.created_at"
      :score="reportScore"
      :dimensions="chartDimensions"
      :html="reportHtml"
    >
      <template #cover-actions>
          <button v-if="isLocalReportTesting" class="secondary report-regenerate" type="button" :disabled="regeneratingReport" @click="regenerateTestReport">
            {{ regeneratingReport ? "重新生成中..." : "重新生成测试报告" }}
          </button>
      </template>
    </CustomerReportView>
    <div v-else class="loading">报告加载中...</div>
  </main>

  <main v-else class="client-shell">
    <section class="diagnosis-panel">
      <header class="client-header">
        <div>
          <p class="eyebrow">AI 原生企业转型诊断</p>
          <h1>3-5 分钟完成企业就绪度自测</h1>
        </div>
        <Sparkles />
      </header>

      <div v-if="error" class="alert">{{ error }}</div>

      <div v-if="step === 'intro'" class="intro-grid">
        <div class="intro-copy">
          <p>完成企业信息与当前诊断题库后，系统会生成结构化诊断报告，包含核心发现、能力画像、题项排序和下一步咨询建议。</p>
          <button class="primary" @click="begin"><FileText :size="18" /> 开始自测</button>
        </div>
        <div class="signal-map" aria-hidden="true">
          <span v-for="item in ['客户', '业务', '组织', '流程', '数据', '智能']" :key="item">{{ item }}</span>
        </div>
      </div>

      <form v-if="step === 'info'" class="form-grid" @submit.prevent="submitLead">
        <label>公司名称<input v-model="leadForm.company_name" required /></label>
        <label>所在城市<input v-model="leadForm.city" required placeholder="例如：广东省深圳市" /></label>
        <label>行业<select v-model="leadForm.industry"><option v-for="item in industries" :key="item">{{ item }}</option></select></label>
        <label>企业规模<select v-model="leadForm.company_size"><option v-for="item in companySizes" :key="item">{{ item }}</option></select></label>
        <label>年营收<select v-model="leadForm.annual_revenue"><option v-for="item in revenues" :key="item">{{ item }}</option></select></label>
        <label>姓名<input v-model="leadForm.contact_name" required /></label>
        <label>职位<input v-model="leadForm.position" required /></label>
        <label>手机号<input v-model="leadForm.phone" inputmode="numeric" maxlength="11" placeholder="请输入 11 位手机号" @input="syncPhoneWechat" /></label>
        <div class="report-email-field">
          <label class="report-email-label" for="diagnostic-email">诊断报告接收邮箱 <em>诊断邮箱</em></label>
          <input id="diagnostic-email" v-model="leadForm.email" type="email" required placeholder="name@example.com" />
          <span class="field-hint">请填写真实可收信邮箱，完整诊断报告和生成文件会发送到这里。</span>
        </div>
        <label>微信<input v-model="leadForm.wechat" placeholder="选填" /></label>
        <label class="check wide" style="border:none;background:none;padding:0;margin-top:-8px">
          <input v-model="phoneWechatSame" type="checkbox" @change="syncPhoneWechat" /> 微信与手机同号
        </label>
        <fieldset class="focus-field wide">
          <legend>当前 AI 转型关注点</legend>
          <p>可以多选，选择最接近当前诉求的方向即可。</p>
          <div class="focus-options">
            <label v-for="item in aiFocusOptions" :key="item" class="focus-option">
              <input v-model="selectedAiFocus" type="checkbox" :value="item" />
              <span>{{ item }}</span>
            </label>
          </div>
          <label class="focus-other">
            其他补充
            <input v-model="aiFocusOther" placeholder="例如：想先了解 AI 项目投入预算、落地周期等" />
          </label>
        </fieldset>
        <label class="check wide"><input v-model="leadForm.privacy_accepted" type="checkbox" /> 我同意用于生成诊断报告和后续顾问联系</label>
        <button class="primary wide" :disabled="busy">{{ busy ? "提交中..." : "进入问卷" }}</button>
      </form>

      <section v-if="step === 'questionnaire' && currentModule" class="questionnaire">
        <div class="progress-row">
          <div>
            <strong class="progress-title">
              <span class="phase-badge">阶段 {{ moduleIndex + 1 }} / {{ modules.length }}</span>
              {{ currentModule.name }}
              <span class="score-badge">{{ currentModule.max_score }}分</span>
            </strong>
            <span>{{ currentModule.description }}</span>
            <span v-if="draftSaved" class="draft-indicator">已自动保存</span>
          </div>
          <strong>{{ answeredCount }}/{{ questions.length }}</strong>
        </div>
        <div class="progress-bar"><span :style="{ width: `${progress * 100}%` }" /></div>

        <div class="module-nav">
          <button
            v-for="(m, i) in modules"
            :key="m.id"
            type="button"
            class="module-dot"
            :class="{ active: i === moduleIndex, done: moduleDone(m) }"
            :aria-label="`跳转到阶段 ${i + 1}：${m.name}`"
            @click="goToModule(i)"
          >
            {{ i + 1 }}
          </button>
        </div>

        <div class="question-list">
          <div v-for="(question, qIndex) in currentModule.questions" :id="`question-${question.id}`" :key="question.id" class="question-row">
            <div class="question-copy">
              <p class="question-text">{{ getGlobalIndex(currentModule, qIndex) }}. {{ question.text }}</p>
              <div class="score-options">
                <label
                  v-for="label in parseOptionLabels(question.option_text)"
                  :key="label.value"
                  class="score-option"
                  :class="{ selected: isAnswerSelected(question.id, label.value) }"
                >
                  <input
                    class="score-radio"
                    type="radio"
                    :name="`question-${question.id}`"
                    :checked="isAnswerSelected(question.id, label.value)"
                    @change="selectAnswer(question.id, label.value)"
                  />
                  <span class="option-score">{{ label.value }}</span>
                  <span class="option-label">{{ label.label }}</span>
                  <span class="option-check"><Check :size="16" /></span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <footer class="step-actions">
          <button class="secondary" :disabled="moduleIndex === 0" @click="goPrevModule"><ChevronLeft :size="18" /> 上一组</button>
          <span class="step-hint">{{ moduleIndex + 1 }} / {{ modules.length }}</span>
          <button v-if="moduleIndex < modules.length - 1" class="primary" @click="goNextModule">下一组 <ChevronRight :size="18" /></button>
          <button v-else class="primary" :disabled="busy" @click="submitQuestionnaire">
            {{ busy ? "提交中..." : answeredCount < questions.length ? `还剩 ${questions.length - answeredCount} 题未答` : "提交并邮件领取报告" }}
          </button>
        </footer>
      </section>

      <section v-if="step === 'submitted'" class="submitted-card">
        <div class="submitted-icon"><Check :size="34" /></div>
        <h2>正在生成您的诊断报告</h2>
        <p>报告完成后会自动为您打开，同时发送至：</p>
        <strong>{{ leadForm.email }}</strong>
        <div v-if="reportFailure" class="queue-status" role="status">
          <span class="queue-dot" aria-hidden="true"></span>
          {{ reportFailure }}
        </div>
        <p v-if="!reportFailure && reportWaitSeconds < 60" class="submitted-note">正在进行 AI 分析，请保持当前页面开启。</p>
        <p v-else-if="!reportFailure" class="submitted-note">您的诊断资料已收到，报告正在进一步审核，完成后将发送至您的邮箱。</p>
        <button class="secondary" type="button" @click="restartFlow">重新填写</button>
      </section>

      <CustomerReportView
        v-if="step === 'report' && activeReport"
        :company-name="reportCompanyName(reportTitle)"
        :report-id="activeReport.id"
        :created-at="reportDate"
        :score="reportScore"
        :dimensions="chartDimensions"
        :html="reportHtml"
      >
        <template #cover-actions>
            <button v-if="isLocalReportTesting" class="secondary report-regenerate" type="button" :disabled="regeneratingReport" @click="regenerateTestReport">
              {{ regeneratingReport ? "重新生成中..." : "重新生成测试报告" }}
            </button>
        </template>
      </CustomerReportView>
    </section>
  </main>

  <div v-if="leadAdvancedFilterOpen" class="modal-backdrop" @click.self="cancelLeadAdvancedFilters">
    <form
      ref="leadAdvancedFilterDialog"
      class="lead-filter-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="lead-filter-dialog-title"
      aria-describedby="lead-filter-dialog-description"
      @submit.prevent="submitLeadAdvancedFilters"
      @keydown="handleLeadAdvancedFilterKeydown"
    >
      <header>
        <div>
          <p class="eyebrow">线索列表</p>
          <h2 id="lead-filter-dialog-title">更多筛选</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭更多筛选" @click="cancelLeadAdvancedFilters"><X :size="18" /></button>
      </header>
      <p id="lead-filter-dialog-description" class="lead-filter-dialog-description">选择需要的条件后点击“应用筛选”，列表与筛选结果导出将使用同一组条件。</p>
      <div class="lead-filter-dialog-grid">
        <label>
          行业
          <select v-model="leadAdvancedFilterDraft.industry">
            <option v-for="item in leadIndustryOptions" :key="item">{{ item }}</option>
          </select>
        </label>
        <label>
          线索等级
          <select v-model="leadAdvancedFilterDraft.leadLevel">
            <option value="">全部</option>
            <option v-for="(label, value) in leadLevelLabels" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <label>
          查看状态
          <select v-model="leadAdvancedFilterDraft.viewStatus">
            <option value="">全部</option>
            <option value="unviewed">尚未查看</option>
            <option value="viewed">已经查看</option>
          </select>
        </label>
        <label>
          导出状态
          <select v-model="leadAdvancedFilterDraft.exportStatus">
            <option value="">全部</option>
            <option value="unexported">未导出</option>
            <option value="exported">已导出</option>
          </select>
        </label>
      </div>
      <footer class="lead-filter-dialog-actions">
        <button class="secondary" type="button" @click="cancelLeadAdvancedFilters">取消</button>
        <button class="secondary" type="button" @click="clearLeadAdvancedFilters">重置筛选</button>
        <button class="primary" type="submit">应用筛选</button>
      </footer>
    </form>
  </div>

  <div v-if="leadRuleDialogOpen" class="modal-backdrop" @click.self="leadRuleDialogOpen = false">
    <section class="rule-dialog" role="dialog" aria-modal="true" aria-labelledby="lead-rule-title">
      <header>
        <h2 id="lead-rule-title">线索评分规则</h2>
        <button class="secondary" type="button" @click="leadRuleDialogOpen = false">关闭</button>
      </header>

      <div class="rule-block">
        <h3>等级：跟进优先级</h3>
        <p>等级用于判断客户是否值得优先联系，不等同于诊断报告里的成熟度等级。</p>
        <ul>
          <li><strong>HIGH 高意向：</strong>客户填写了手机号或微信，并且至少 2 个诊断维度得分率低于 50%。说明客户有联系方式，且短板较明显，建议优先跟进。</li>
          <li><strong>MEDIUM 中意向：</strong>客户填写了手机号或微信，但低分维度不足 2 个。说明可以正常跟进，但优先级低于 HIGH。</li>
          <li><strong>LOW 低意向：</strong>客户没有填写手机号和微信。当前前端已要求手机号或微信至少填写一项，因此 LOW 多见于旧数据或测试数据。</li>
        </ul>
      </div>

      <p class="rule-note">当前规则是首版自动判定逻辑，后续可以继续加入企业规模、年营收、行业权重、职位角色等因素，让线索优先级更贴近真实销售判断。</p>
    </section>
  </div>

  <div v-if="questionBankDialog" class="modal-backdrop" @click.self="questionBankDialog = null">
    <form v-if="questionBankDialog === 'module'" class="question-bank-dialog" @submit.prevent="createQuestionModule">
      <header>
        <div><p class="eyebrow">题库管理</p><h2>新增题库</h2></div>
        <button class="secondary" type="button" @click="questionBankDialog = null">取消</button>
      </header>
      <label>题库名称<input v-model="questionModuleForm.name" required maxlength="120" placeholder="例如：客户运营能力" /></label>
      <label>题库说明<textarea v-model="questionModuleForm.description" maxlength="500" placeholder="选填" /></label>
      <div class="question-bank-number-grid">
        <label>题库总分<input v-model.number="questionModuleForm.max_score" type="number" min="1" max="1000" required /></label>
        <label>展示顺序<input v-model.number="questionModuleForm.sort_order" type="number" min="1" required /></label>
      </div>
      <button class="primary" :disabled="questionBankSaving"><Plus :size="18" /> {{ questionBankSaving ? "创建中..." : "创建题库" }}</button>
    </form>

    <form v-else class="question-bank-dialog" @submit.prevent="createQuestion">
      <header>
        <div><p class="eyebrow">{{ questionForm.module_code }}</p><h2>新增题目</h2></div>
        <button class="secondary" type="button" @click="questionBankDialog = null">取消</button>
      </header>
      <label>题目内容<textarea v-model="questionForm.text" required maxlength="1000" placeholder="请输入诊断问题" /></label>
      <label>评估维度<input v-model="questionForm.dimension" maxlength="120" placeholder="例如：客户运营能力" /></label>
      <label>选项说明<textarea v-model="questionForm.option_text" required maxlength="1000" /></label>
      <div class="question-bank-number-grid">
        <label>题目满分<input v-model.number="questionForm.max_score" type="number" min="1" max="4" required /></label>
        <label>展示顺序<input v-model.number="questionForm.sort_order" type="number" min="1" required /></label>
      </div>
      <button class="primary" :disabled="questionBankSaving"><Plus :size="18" /> {{ questionBankSaving ? "创建中..." : "创建题目" }}</button>
    </form>
  </div>

</template>

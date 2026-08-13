<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import {
  ArrowLeft,
  ArrowDownToLine,
  BarChart3,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  Lock,
  LogOut,
  Plus,
  ShieldCheck,
  Sparkles,
  Trash2
} from "lucide-vue-next";
import ReportCharts from "./components/ReportCharts.vue";
import { adminNotice, error } from "./composables/feedback";
import { useAdmin } from "./composables/useAdmin";
import { useQuestionnaire } from "./composables/useQuestionnaire";
import { useReportView } from "./composables/useReportView";
import { isAdmin, reportToken } from "./utils/appPaths";
import { bucketPct, completionRate, formatDate, formatDateTime, pct } from "./utils/format";

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
  leadIndustryFilter,
  leadPageSize,
  leadPage,
  leadRuleDialogOpen,
  leadDetailOpen,
  leadDetailLoading,
  selectedLeadDetail,
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
  leadWordExporting,
  questionModuleForm,
  questionForm,
  canExportLeads,
  canManageQuestionBank,
  leadIndustryOptions,
  sourceLabel,
  filteredLeads,
  leadTotalPages,
  pagedLeads,
  leadPageStart,
  leadPageEnd,
  leadDetailReportHtml,
  selectedLeadScoreRate,
  loginAdmin,
  loadAdminShell,
  loadAdminTab,
  goLeadPage,
  openLeadDetail,
  closeLeadDetail,
  updateLeadDiagnosticEmail,
  exportLeads,
  exportLeadWord,
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
} = useAdmin();

onMounted(async () => {
  window.addEventListener("beforeunload", handleBeforeUnload);
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
});

onBeforeUnmount(clearReportPolling);
</script>

<template>
  <div v-if="missingNoticeVisible" class="top-message" role="status" aria-live="polite">
    <span class="top-message-icon">!</span>
    <span>{{ missingNoticeMessage }}</span>
  </div>

  <main v-if="isAdmin && !adminToken" class="login-shell">
    <form class="login-box" @submit.prevent="loginAdmin">
      <Lock :size="28" />
      <h1>后台登录</h1>
      <div v-if="error" class="alert">{{ error }}</div>
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
      <div v-if="error" class="admin-feedback error-feedback">{{ error }}</div>
      <div v-if="adminNotice" class="admin-feedback success-feedback">{{ adminNotice }}</div>

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
            <button v-if="canExportLeads" class="secondary" type="button" :disabled="leadsExporting" @click="exportLeads"><ArrowDownToLine :size="18" /> {{ leadsExporting ? "导出中..." : "导出" }}</button>
          </div>
        </div>
        <div class="lead-toolbar">
          <label>
            时间排序
            <select v-model="leadSortOrder">
              <option value="newest">最新优先</option>
              <option value="oldest">最早优先</option>
            </select>
          </label>
          <label>
            行业
            <select v-model="leadIndustryFilter">
              <option v-for="item in leadIndustryOptions" :key="item">{{ item }}</option>
            </select>
          </label>
          <label>
            每页
            <select v-model.number="leadPageSize">
              <option :value="10">10 条</option>
              <option :value="15">15 条</option>
              <option :value="30">30 条</option>
              <option :value="50">50 条</option>
            </select>
          </label>
          <div class="lead-count">共 {{ filteredLeads.length }} 条</div>
        </div>
        <div class="leads-table-wrap">
          <table class="leads-table">
            <thead><tr><th>公司</th><th>行业</th><th>联系人</th><th>职位</th><th>联系</th><th>等级</th><th>最近处理时间</th></tr></thead>
            <tbody>
              <tr v-for="lead in pagedLeads" :key="lead.id" class="clickable-row" tabindex="0" @click="openLeadDetail(lead)" @keydown.enter="openLeadDetail(lead)">
                <td :title="lead.company_name || ''">{{ lead.company_name }}</td>
                <td :title="lead.industry || ''">{{ lead.industry }}</td>
                <td :title="lead.contact_name || ''">{{ lead.contact_name }}</td>
                <td :title="lead.position || ''">{{ lead.position }}</td>
                <td :title="lead.phone || lead.wechat || ''">{{ lead.phone || lead.wechat }}</td>
                <td><span class="pill" :class="lead.lead_level">{{ lead.lead_level }}</span></td>
                <td>{{ formatDateTime(lead.last_activity_at || lead.updated_at || lead.created_at) }}</td>
              </tr>
              <tr v-if="!pagedLeads.length">
                <td colspan="7" class="empty-cell">暂无符合条件的线索</td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="pagination">
          <span>显示 {{ leadPageStart }}-{{ leadPageEnd }} / {{ filteredLeads.length }}</span>
          <div>
            <button class="secondary" :disabled="leadPage <= 1" @click="goLeadPage(-1)"><ChevronLeft :size="16" /> 上一页</button>
            <strong>{{ leadPage }} / {{ leadTotalPages }}</strong>
            <button class="secondary" :disabled="leadPage >= leadTotalPages" @click="goLeadPage(1)">下一页 <ChevronRight :size="16" /></button>
          </div>
        </footer>
      </section>

      <section v-else class="table-section lead-detail-page" aria-labelledby="lead-detail-title">
        <header class="lead-detail-page-header">
          <div>
            <p class="eyebrow">客户详情</p>
            <h2 id="lead-detail-title">{{ selectedLeadDetail?.lead.company_name || "客户详情" }}</h2>
          </div>
          <div class="lead-detail-actions">
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
            <h3>基本信息</h3>
            <div class="detail-grid">
              <div><span>公司</span><strong>{{ selectedLeadDetail.lead.company_name || "-" }}</strong></div>
              <div><span>行业</span><strong>{{ selectedLeadDetail.lead.industry || "-" }}</strong></div>
              <div><span>规模</span><strong>{{ selectedLeadDetail.lead.company_size || "-" }}</strong></div>
              <div><span>年营收</span><strong>{{ selectedLeadDetail.lead.annual_revenue || "-" }}</strong></div>
              <div><span>联系人</span><strong>{{ selectedLeadDetail.lead.contact_name || "-" }}</strong></div>
              <div><span>职位</span><strong>{{ selectedLeadDetail.lead.position || "-" }}</strong></div>
              <div><span>手机号</span><strong>{{ selectedLeadDetail.lead.phone || "-" }}</strong></div>
              <div><span>邮箱</span><strong>{{ selectedLeadDetail.lead.email || "-" }}</strong></div>
              <div><span>微信</span><strong>{{ selectedLeadDetail.lead.wechat || "-" }}</strong></div>
              <div><span>来源</span><strong :title="selectedLeadDetail.lead.source_code || ''">{{ sourceLabel(selectedLeadDetail.lead.source_code) }}</strong></div>
            </div>
            <div class="diagnostic-email-editor">
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
              <div><span>线索等级</span><strong><span class="pill" :class="selectedLeadDetail.lead.lead_level">{{ selectedLeadDetail.lead.lead_level }}</span></strong></div>
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
            <h3>AI 分析报告</h3>
            <div v-if="selectedLeadDetail.report?.html_content" class="detail-report-html" v-html="leadDetailReportHtml"></div>
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
    <section v-if="publicReport" class="report-view">
      <!-- Hero -->
      <header class="report-hero">
        <div class="hero-content">
          <p class="hero-badge">
            <Sparkles :size="16" /> AI 原生企业转型诊断报告
          </p>
          <h1 class="hero-title">{{ reportTitle }}</h1>
          <div class="hero-meta">
            <span>报告编号  {{ publicReport.public_token.slice(0, 8).toUpperCase() }}</span>
            <span class="meta-divider"></span>
            <span>{{ formatDate(publicReport.created_at) }}</span>
          </div>
        </div>
      </header>

      <!-- Score Cards -->
      <div v-if="reportScore" class="score-strip">
        <div class="score-card score-card--total">
          <span class="score-card-label">诊断总分</span>
          <strong>{{ reportScore.total }}<em>/{{ reportScore.max }}</em></strong>
          <div class="score-card-bar"><span :style="{ width: `${Math.round(reportScore.rate * 100)}%` }"></span></div>
        </div>
        <div class="score-card score-card--rate">
          <span class="score-card-label">综合得分率</span>
          <strong>{{ Math.round(reportScore.rate * 100) }}<em>%</em></strong>
          <div class="score-card-ring">
            <svg viewBox="0 0 36 36"><path class="ring-bg" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/><path class="ring-fill" :stroke-dasharray="`${Math.round(reportScore.rate * 100)}, 100`" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/></svg>
          </div>
        </div>
      </div>

      <section v-if="currentProblemAnalysis.length" class="ai-problem-panel">
        <header>
          <div><p class="eyebrow">AI Analysis</p><h2>AI 当前问题分析</h2></div>
          <span>基于本次答题结果</span>
        </header>
        <div v-if="aiProblemAnalysis" class="ai-problem-summary ai-problem-ai-text" v-html="aiProblemAnalysisHtml" />
        <p v-else class="ai-problem-summary">{{ reportDemandSummary || "正在基于本次答题结果生成企业问题分析。" }}</p>
        <div class="ai-problem-list">
          <article v-for="(item, index) in currentProblemAnalysis" :key="item.name">
            <span class="problem-order">0{{ index + 1 }}</span>
            <div><strong>{{ item.name }}</strong></div>
            <b>{{ item.scoreRate }}%</b>
          </article>
        </div>
      </section>

      <!-- Charts -->
      <ReportCharts v-if="chartDimensions.length" :dimensions="chartDimensions" />
      <div v-else class="loading">图表数据加载中...</div>

      <!-- Report Content -->
      <article class="report-html" v-html="reportHtml" />
    </section>
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
          <p>完成企业信息与 68 题量表后，系统会生成结构化诊断报告，包含总分等级、短板维度、优先 AI 场景和下一步咨询建议。</p>
          <button class="primary" @click="begin"><FileText :size="18" /> 开始自测</button>
        </div>
        <div class="signal-map" aria-hidden="true">
          <span v-for="item in ['客户', '业务', '组织', '流程', '数据', '智能']" :key="item">{{ item }}</span>
        </div>
      </div>

      <form v-if="step === 'info'" class="form-grid" @submit.prevent="submitLead">
        <label>公司名称<input v-model="leadForm.company_name" required /></label>
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
        <p v-if="reportWaitSeconds < 20" class="submitted-note">正在进行 AI 分析，请保持当前页面开启。</p>
        <p v-else class="submitted-note">当前访问量较高，报告仍会在生成完成后发送至邮箱；您可以稍后通过邮件中的链接查看。</p>
      </section>

      <section v-if="step === 'report' && activeReport" class="report-view">
        <!-- Hero -->
        <header class="report-hero">
          <div class="hero-content">
            <p class="hero-badge">
              <Sparkles :size="16" /> AI 原生企业转型诊断报告
            </p>
            <h1 class="hero-title">{{ reportTitle }}</h1>
            <div class="hero-meta">
              <span>报告编号  {{ pdfToken.slice(0, 8).toUpperCase() }}</span>
              <span class="meta-divider"></span>
              <span>{{ formatDate(reportDate) }}</span>
            </div>
          </div>
        </header>

        <!-- Score Cards -->
        <div v-if="reportScore" class="score-strip">
          <div class="score-card score-card--total">
            <span class="score-card-label">诊断总分</span>
            <strong>{{ reportScore.total }}<em>/{{ reportScore.max }}</em></strong>
            <div class="score-card-bar"><span :style="{ width: `${Math.round(reportScore.rate * 100)}%` }"></span></div>
          </div>
          <div class="score-card score-card--rate">
            <span class="score-card-label">综合得分率</span>
            <strong>{{ Math.round(reportScore.rate * 100) }}<em>%</em></strong>
            <div class="score-card-ring">
              <svg viewBox="0 0 36 36"><path class="ring-bg" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/><path class="ring-fill" :stroke-dasharray="`${Math.round(reportScore.rate * 100)}, 100`" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/></svg>
            </div>
          </div>
        </div>

        <section v-if="currentProblemAnalysis.length" class="ai-problem-panel">
          <header>
            <div><p class="eyebrow">AI Analysis</p><h2>AI 当前问题分析</h2></div>
            <span>基于本次答题结果</span>
          </header>
          <div v-if="aiProblemAnalysis" class="ai-problem-summary ai-problem-ai-text" v-html="aiProblemAnalysisHtml" />
          <p v-else class="ai-problem-summary">{{ reportDemandSummary || "正在基于本次答题结果生成企业问题分析。" }}</p>
          <div class="ai-problem-list">
            <article v-for="(item, index) in currentProblemAnalysis" :key="item.name">
              <span class="problem-order">0{{ index + 1 }}</span>
              <div><strong>{{ item.name }}</strong></div>
              <b>{{ item.scoreRate }}%</b>
            </article>
          </div>
        </section>

        <!-- Charts -->
        <ReportCharts :dimensions="chartDimensions" />

        <!-- Report Content -->
        <article class="report-html" v-html="reportHtml" />
      </section>
    </section>
  </main>

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

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch, type Component } from "vue";
import {
  ArrowDownToLine,
  BarChart3,
  BookOpen,
  BriefcaseBusiness,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  LayoutDashboard,
  Lock,
  LogOut,
  Mail,
  Plus,
  QrCode,
  ShieldCheck,
  Sparkles,
  Trash2,
  Users
} from "lucide-vue-next";
import { api } from "./api";
import type { AnalyticsSummary, CaseStudy, ChannelSource, Lead, LeadDetail, QuestionModule, Report, ScoreResponse, User } from "./types";
import ReportCharts from "./components/ReportCharts.vue";

type Step = "intro" | "info" | "questionnaire" | "submitted" | "report";
type AdminTab = "overview" | "leads" | "questions" | "cases" | "users" | "channels";
type LeadSortOrder = "newest" | "oldest";
type LeadFormState = {
  company_name: string;
  industry: string;
  company_size: string;
  annual_revenue: string;
  contact_name: string;
  position: string;
  phone: string;
  email: string;
  wechat: string;
  ai_focus: string;
  privacy_accepted: boolean;
  contact_authorized: boolean;
};

const industries = ["制造业", "消费品", "零售电商", "教育培训", "医疗健康", "专业服务", "其他"];
const companySizes = ["1-200人", "200-500人", "500-1000人", "2000-5000人", "5000人以上"];
const revenues = ["暂不填写", "<1亿", "1-5亿", "5-10亿", ">10亿"];
const aiFocusOptions = [
  "想提升获客、销售转化和客户跟进效率",
  "想用 AI 优化内部流程、审批和协同效率",
  "想搭建企业知识库，让员工更快找到资料和答案",
  "想做智能客服、售后支持或客户服务自动化",
  "想用 AI 辅助内容生产、营销物料和方案撰写",
  "想先判断公司适合从哪些 AI 场景开始"
];

const isAdmin = window.location.pathname.startsWith("/admin");
const reportToken = window.location.pathname.match(/^\/report\/([^/]+)/)?.[1] || "";

const step = ref<Step>("intro");
const sessionToken = ref<string | null>(localStorage.getItem("diagnosis_session"));
const leadId = ref<number | null>(Number(localStorage.getItem("diagnosis_lead_id")) || null);
const submissionId = ref<number | null>(Number(localStorage.getItem("submission_id")) || null);
const modules = ref<QuestionModule[]>([]);
const moduleIndex = ref(Number(localStorage.getItem("diagnosis_module_index")) || 0);
const answers = ref<Record<number, number>>(JSON.parse(localStorage.getItem("diagnosis_answers") || "{}"));
const score = ref<ScoreResponse | null>(null);
const report = ref<Report | null>(null);
const publicReport = ref<Report | null>(null);
const error = ref("");
const adminNotice = ref("");
const busy = ref(false);
const draftSaved = ref(false);
const emailDialogOpen = ref(false);
const reportEmail = ref("");
const emailSending = ref(false);
const emailNotice = ref("");
const reportWaitSeconds = ref(0);
const reportPollTimer = ref<number | null>(null);
const reportWaitTimer = ref<number | null>(null);
const missingNoticeVisible = ref(false);
const missingNoticeMessage = ref("");
const missingNoticeTimer = ref<number | null>(null);

const defaultLeadForm: LeadFormState = {
  company_name: "",
  industry: "制造业",
  company_size: "1-200人",
  annual_revenue: "暂不填写",
  contact_name: "",
  position: "",
  phone: "",
  email: "",
  wechat: "",
  ai_focus: "",
  privacy_accepted: false,
  contact_authorized: false
};

function loadSavedLeadForm(): LeadFormState {
  const saved = localStorage.getItem("diagnosis_lead_form");
  if (!saved) return { ...defaultLeadForm };
  try {
    const parsed = { ...defaultLeadForm, ...JSON.parse(saved) };
    if (!companySizes.includes(parsed.company_size)) {
      parsed.company_size = defaultLeadForm.company_size;
    }
    return parsed;
  } catch {
    return { ...defaultLeadForm };
  }
}

const leadForm = reactive<LeadFormState>(loadSavedLeadForm());

const phoneWechatSame = ref(false);
const selectedAiFocus = ref<string[]>([]);
const aiFocusOther = ref("");

function restoreAiFocus() {
  const saved = leadForm.ai_focus
    .split("；")
    .map((item) => item.trim())
    .filter(Boolean);
  selectedAiFocus.value = saved.filter((item) => aiFocusOptions.includes(item));
  aiFocusOther.value = saved.filter((item) => !aiFocusOptions.includes(item)).join("；");
}

function syncAiFocus() {
  leadForm.ai_focus = [...selectedAiFocus.value, aiFocusOther.value.trim()].filter(Boolean).join("；");
}

restoreAiFocus();

function syncPhoneWechat() {
  if (phoneWechatSame.value && leadForm.phone) {
    leadForm.wechat = leadForm.phone;
  } else if (!phoneWechatSame.value) {
    leadForm.wechat = "";
  }
}

function isValidPhone(phone: string): boolean {
  return /^1[3-9]\d{9}$/.test(phone.trim());
}

function parseOptionLabels(optionText: string | null | undefined): { value: number; label: string }[] {
  if (!optionText) return [];
  return optionText.split("；").map((item) => {
    const [num, ...labelParts] = item.trim().split("=");
    return { value: parseInt(num), label: labelParts.join("=").trim() || num };
  }).filter((item) => !isNaN(item.value));
}

function getGlobalIndex(module: QuestionModule, qIndex: number): number {
  let count = 0;
  for (const m of modules.value) {
    if (m.id === module.id) break;
    count += m.questions.length;
  }
  return count + qIndex + 1;
}

const adminToken = ref(localStorage.getItem("admin_token"));
const adminUser = ref<User | null>(null);
const adminEmail = ref("admin@example.com");
const adminPassword = ref("");
const adminTab = ref<AdminTab>("overview");
const analytics = ref<AnalyticsSummary | null>(null);
const leads = ref<Lead[]>([]);
const leadSortOrder = ref<LeadSortOrder>("newest");
const leadStrategyFilter = ref("全部打法");
const leadIndustryFilter = ref("全部行业");
const leadPageSize = ref(10);
const leadPage = ref(1);
const leadRuleDialogOpen = ref(false);
const leadDetailOpen = ref(false);
const leadDetailLoading = ref(false);
const selectedLeadDetail = ref<LeadDetail | null>(null);
const adminQuestions = ref<QuestionModule[]>([]);
const cases = ref<CaseStudy[]>([]);
const users = ref<User[]>([]);

const caseForm = reactive({
  title: "",
  industry: "通用",
  function_area: "",
  module_code: "M01",
  description: "",
  expected_benefit: "",
  priority_tag: "闪电战"
});

const userForm = reactive({
  email: "",
  name: "",
  role: "sales",
  password: ""
});

const questions = computed(() => modules.value.flatMap((module) => module.questions));
const answeredCount = computed(() => Object.keys(answers.value).length);
const currentModule = computed(() => modules.value[moduleIndex.value]);
const progress = computed(() => (questions.value.length ? answeredCount.value / questions.value.length : 0));
const activeReport = computed(() => report.value || publicReport.value);

const channels = ref<ChannelSource[]>([]);
const channelForm = reactive({ code: "", name: "", description: "" });

const adminTabs: { key: AdminTab; label: string; icon: Component }[] = [
  { key: "overview", label: "统计", icon: LayoutDashboard },
  { key: "leads", label: "线索", icon: BriefcaseBusiness },
  { key: "questions", label: "题库", icon: BookOpen },
  { key: "cases", label: "案例", icon: FileText },
  { key: "users", label: "账号", icon: Users },
  { key: "channels", label: "渠道", icon: QrCode }
];

function sourceFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("source") || "default";
}

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function bucketPct(count: number, buckets: { count: number }[]) {
  const max = Math.max(1, ...buckets.map((item) => item.count));
  return `${Math.max(4, Math.round((count / max) * 100))}%`;
}

function completionRate(value: number | undefined) {
  return `${Math.round((value || 0) * 100)}%`;
}

function answersToList() {
  return Object.entries(answers.value).map(([question_id, itemScore]) => ({ question_id: Number(question_id), score: Number(itemScore) }));
}

function persistLeadForm() {
  localStorage.setItem("diagnosis_lead_form", JSON.stringify({ ...leadForm }));
}

async function bootClient() {
  if (!sessionToken.value) {
    const created = await api.createSession(sourceFromUrl());
    sessionToken.value = created.session_token;
    localStorage.setItem("diagnosis_session", created.session_token);
  }

  if (await restoreSubmittedReport()) return;

  modules.value = await api.questions();
  if (moduleIndex.value >= modules.value.length) {
    moduleIndex.value = 0;
    localStorage.setItem("diagnosis_module_index", "0");
  }

  // 恢复中断的答题进度
  const savedStep = localStorage.getItem("diagnosis_step");
  if (savedStep === "questionnaire" && submissionId.value) {
    step.value = "questionnaire";
  } else if (savedStep === "info" || localStorage.getItem("diagnosis_lead_form")) {
    step.value = "info";
  }
}

function isReportReady(item: Report): boolean {
  return Boolean(item.html_content && ["generated", "fallback"].includes(item.status));
}

function clearReportPolling() {
  if (reportPollTimer.value !== null) {
    window.clearInterval(reportPollTimer.value);
    reportPollTimer.value = null;
  }
  if (reportWaitTimer.value !== null) {
    window.clearInterval(reportWaitTimer.value);
    reportWaitTimer.value = null;
  }
}

function openReportPage(token: string) {
  clearReportPolling();
  localStorage.setItem("diagnosis_report_token", token);
  localStorage.removeItem("diagnosis_step");
  window.location.assign(`/report/${token}`);
}

async function checkSubmittedReport(): Promise<boolean> {
  if (!sessionToken.value) return false;
  try {
    let currentReport: Report;
    try {
      currentReport = submissionId.value
        ? await api.submissionReport(submissionId.value, sessionToken.value)
        : await api.latestSessionReport(sessionToken.value);
    } catch {
      currentReport = await api.latestSessionReport(sessionToken.value);
    }
    report.value = currentReport;
    localStorage.setItem("diagnosis_report_token", currentReport.public_token);
    if (isReportReady(currentReport)) {
      openReportPage(currentReport.public_token);
      return true;
    }
  } catch {
    // 尚未创建报告时继续保留在原来的填写/答题流程。
  }
  return false;
}

function startReportPolling() {
  clearReportPolling();
  reportWaitSeconds.value = 0;
  reportWaitTimer.value = window.setInterval(() => {
    reportWaitSeconds.value += 1;
  }, 1000);
  reportPollTimer.value = window.setInterval(() => {
    void checkSubmittedReport();
  }, 3000);
  window.setTimeout(() => { void checkSubmittedReport(); }, 400);
}

async function restoreSubmittedReport(): Promise<boolean> {
  const hasReport = await checkSubmittedReport();
  if (hasReport) return true;
  if (localStorage.getItem("diagnosis_report_token")) {
    step.value = "submitted";
    persistStep();
    startReportPolling();
    return true;
  }
  return false;
}

async function begin() {
  step.value = "info";
  persistStep();
  await api.track("click_start", sessionToken.value);
}

async function submitLead() {
  error.value = "";
  const phone = leadForm.phone.trim();
  const email = leadForm.email.trim();
  const wechat = leadForm.wechat.trim();
  if (phone && !isValidPhone(phone)) {
    error.value = "请输入正确的 11 位手机号";
    return;
  }
  if (!isValidEmail(email)) {
    error.value = "请输入正确的邮箱地址，报告将发送到该邮箱";
    return;
  }
  if (!phone && !wechat) {
    error.value = "手机号或微信至少填写一项";
    return;
  }
  syncAiFocus();
  if (!leadForm.ai_focus.trim()) {
    error.value = "请选择当前最关注的 AI 转型方向";
    return;
  }
  if (!leadForm.privacy_accepted) {
    error.value = "请先勾选同意用于生成诊断报告和后续顾问联系";
    return;
  }
  busy.value = true;
  try {
    const result = await api.submitLead({ ...leadForm, phone, email, wechat, contact_authorized: leadForm.privacy_accepted, session_token: sessionToken.value, source_code: sourceFromUrl() });
    leadId.value = result.lead.id;
    submissionId.value = result.submission_id;
    localStorage.setItem("diagnosis_lead_id", String(result.lead.id));
    localStorage.setItem("submission_id", String(result.submission_id));
    step.value = "questionnaire";
    persistStep();
    await api.track("start_questionnaire", sessionToken.value, result.lead.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "提交失败";
  } finally {
    busy.value = false;
  }
}

function persistStep() {
  localStorage.setItem("diagnosis_step", step.value);
}

function moduleDone(module: QuestionModule): boolean {
  return module.questions.every((q) => answers.value[q.id] !== undefined);
}

function isAnswerSelected(questionId: number, value: number): boolean {
  return Number(answers.value[questionId]) === value;
}

function firstMissingQuestion(module: QuestionModule) {
  return module.questions.find((q) => answers.value[q.id] === undefined);
}

async function focusQuestion(questionId: number) {
  await nextTick();
  const target = document.getElementById(`question-${questionId}`);
  target?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function showMissingNotice(message: string) {
  missingNoticeMessage.value = message;
  missingNoticeVisible.value = true;
  if (missingNoticeTimer.value !== null) {
    window.clearTimeout(missingNoticeTimer.value);
  }
  missingNoticeTimer.value = window.setTimeout(() => {
    missingNoticeVisible.value = false;
    missingNoticeTimer.value = null;
  }, 3200);
}

async function showMissingQuestion(module: QuestionModule, index: number) {
  const missing = firstMissingQuestion(module);
  if (!missing) return false;
  const missingCount = module.questions.filter((question) => answers.value[question.id] === undefined).length;
  moduleIndex.value = index;
  localStorage.setItem("diagnosis_module_index", String(index));
  error.value = "";
  showMissingNotice(`当前页面还有 ${missingCount} 题未答，请先完成后再进入下一组。`);
  await focusQuestion(missing.id);
  return true;
}

async function goToModule(index: number) {
  if (index > moduleIndex.value) {
    const blockedIndex = modules.value.findIndex((module, moduleIdx) => moduleIdx < index && !moduleDone(module));
    if (blockedIndex >= 0) {
      await showMissingQuestion(modules.value[blockedIndex], blockedIndex);
      return;
    }
  }
  moduleIndex.value = index;
  localStorage.setItem("diagnosis_module_index", String(index));
  error.value = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function goNextModule() {
  if (!currentModule.value) return;
  if (await showMissingQuestion(currentModule.value, moduleIndex.value)) {
    return;
  }
  if (moduleIndex.value < modules.value.length - 1) {
    await goToModule(moduleIndex.value + 1);
  }
}

function goPrevModule() {
  if (moduleIndex.value > 0) {
    goToModule(moduleIndex.value - 1);
  }
}

async function selectAnswer(questionId: number, value: number) {
  answers.value = { ...answers.value, [questionId]: value };
  localStorage.setItem("diagnosis_answers", JSON.stringify(answers.value));
  if (currentModule.value && !firstMissingQuestion(currentModule.value)) {
    error.value = "";
    missingNoticeVisible.value = false;
  }
  if (submissionId.value) {
    await api.saveDraft(submissionId.value, answersToList()).catch(() => undefined);
  }
  draftSaved.value = true;
  setTimeout(() => { draftSaved.value = false; }, 2000);
}

async function submitQuestionnaire() {
  if (!submissionId.value) return;
  const missing = questions.value.find((question) => answers.value[question.id] === undefined);
  if (missing) {
    const targetIndex = modules.value.findIndex((module) => module.questions.some((question) => question.id === missing.id));
    moduleIndex.value = Math.max(0, targetIndex);
    error.value = "";
    showMissingNotice(`还有题目未填写，已为你跳转到漏答位置：${missing.code}`);
    await focusQuestion(missing.id);
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const result = await api.submitQuestionnaire(submissionId.value, answersToList());
    score.value = result.score;
    report.value = result.report;
    localStorage.setItem("diagnosis_report_token", result.report.public_token);
    step.value = "submitted";
    localStorage.removeItem("diagnosis_answers");
    persistStep();
    await api.track(
      "report_delivery_queued",
      sessionToken.value,
      leadId.value,
      { report_id: result.report.id, email: leadForm.email }
    );
    startReportPolling();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "提交失败";
    await api.track("generate_report_failed", sessionToken.value, leadId.value);
  } finally {
    busy.value = false;
  }
}

async function loadPublicReport() {
  publicReport.value = await api.publicReport(reportToken);
  if (publicReport.value) {
    const score = publicReport.value.score;
    const desc = score
      ? `诊断总分 ${score.total}/260 · 等级 ${score.risk_level} · 得分率 ${Math.round(score.score_rate * 100)}%`
      : "查看 AI 原生企业转型诊断报告";
    updateShareMeta(publicReport.value.title, desc, window.location.href);
  }
}

async function loginAdmin() {
  error.value = "";
  try {
    const result = await api.login(adminEmail.value, adminPassword.value);
    localStorage.setItem("admin_token", result.access_token);
    adminToken.value = result.access_token;
    await loadAdminShell();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "登录失败";
  }
}

async function loadAdminShell() {
  adminUser.value = await api.me();
  await loadAdminTab("overview");
}

async function loadAdminTab(tab: AdminTab) {
  adminTab.value = tab;
  if (tab === "overview") analytics.value = await api.analytics();
  if (tab === "leads") {
    leads.value = await api.leads();
    resetLeadPage();
  }
  if (tab === "questions") adminQuestions.value = await api.adminQuestions();
  if (tab === "cases") cases.value = await api.cases();
  if (tab === "users") users.value = await api.users().catch(() => []);
  if (tab === "channels") channels.value = await api.channels().catch(() => []);
}

function resetLeadPage() {
  leadPage.value = 1;
}

function goLeadPage(direction: number) {
  leadPage.value = Math.min(leadTotalPages.value, Math.max(1, leadPage.value + direction));
}

async function openLeadDetail(lead: Lead) {
  leadDetailOpen.value = true;
  leadDetailLoading.value = true;
  selectedLeadDetail.value = null;
  error.value = "";
  try {
    selectedLeadDetail.value = await api.leadDetail(lead.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载客户详情失败";
    leadDetailOpen.value = false;
  } finally {
    leadDetailLoading.value = false;
  }
}

function logoutAdmin() {
  localStorage.removeItem("admin_token");
  adminToken.value = null;
  adminUser.value = null;
}

const chartDimensions = computed(() => {
  if (score.value?.dimensions?.length) return score.value.dimensions;
  if (publicReport.value?.dimensions?.length) return publicReport.value.dimensions;
  return [];
});

const reportTitle = computed(() => activeReport.value?.title || "");
const reportDate = computed(() => activeReport.value?.created_at || "");
const reportScore = computed(() => {
  if (score.value) return { total: score.value.total_score, max: score.value.max_score, rate: score.value.score_rate, level: score.value.risk_level };
  if (publicReport.value?.score) return { total: publicReport.value.score.total, max: publicReport.value.score.max_score, rate: publicReport.value.score.score_rate, level: publicReport.value.score.risk_level };
  return null;
});
const reportHtml = computed(() => normalizeReportHtml(activeReport.value?.html_content || ""));
const pdfToken = computed(() => activeReport.value?.public_token || "");
const leadDetailReportHtml = computed(() => normalizeReportHtml(selectedLeadDetail.value?.report?.html_content || ""));
const selectedLeadScoreRate = computed(() => {
  const rate = selectedLeadDetail.value?.submission?.score_rate;
  return rate === null || rate === undefined ? "-" : `${Math.round(rate * 100)}%`;
});
const leadStrategyOptions = computed(() => ["全部打法", ...Array.from(new Set(leads.value.map((lead) => lead.priority_strategy || "未判定").filter(Boolean)))]);
const leadIndustryOptions = computed(() => ["全部行业", ...Array.from(new Set(leads.value.map((lead) => lead.industry || "未填写").filter(Boolean)))]);
const filteredLeads = computed(() => {
  return leads.value
    .filter((lead) => leadStrategyFilter.value === "全部打法" || (lead.priority_strategy || "未判定") === leadStrategyFilter.value)
    .filter((lead) => leadIndustryFilter.value === "全部行业" || (lead.industry || "未填写") === leadIndustryFilter.value)
    .sort((a, b) => {
      const diff = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      return leadSortOrder.value === "newest" ? diff : -diff;
    });
});
const leadTotalPages = computed(() => Math.max(1, Math.ceil(filteredLeads.value.length / leadPageSize.value)));
const pagedLeads = computed(() => {
  const safePage = Math.min(leadPage.value, leadTotalPages.value);
  const start = (safePage - 1) * leadPageSize.value;
  return filteredLeads.value.slice(start, start + leadPageSize.value);
});
const leadPageStart = computed(() => filteredLeads.value.length ? (Math.min(leadPage.value, leadTotalPages.value) - 1) * leadPageSize.value + 1 : 0);
const leadPageEnd = computed(() => Math.min(leadPageStart.value + leadPageSize.value - 1, filteredLeads.value.length));

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function openEmailDialog() {
  emailNotice.value = "";
  error.value = "";
  reportEmail.value = "";
  emailDialogOpen.value = true;
}

async function sendReportToEmail() {
  if (!pdfToken.value) return;
  const email = reportEmail.value.trim();
  emailNotice.value = "";
  error.value = "";
  if (!isValidEmail(email)) {
    error.value = "请输入正确的邮箱地址";
    return;
  }
  emailSending.value = true;
  try {
    await api.emailReport(pdfToken.value, email);
    emailNotice.value = "报告已发送到邮箱，请注意查收";
    emailDialogOpen.value = false;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "发送失败";
  } finally {
    emailSending.value = false;
  }
}

function escapeHtmlText(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function inlineMarkdown(value: string): string {
  return escapeHtmlText(value).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function cleanAdvisorText(value: string): string {
  let cleaned = value.trim();
  const markers = ["本次诊断结果显示", "本次诊断显示", "诊断结果显示"];
  const positions = markers.map((marker) => cleaned.indexOf(marker)).filter((index) => index >= 0);
  if (positions.length) {
    cleaned = cleaned.slice(Math.min(...positions));
  }
  return cleaned
    .replace(/^好的，[\s\S]*?\n+/, "")
    .replace(/^---+\s*/, "")
    .replace(/^#{1,6}\s*\*\*.*?报告\*\*\s*/m, "")
    .replace(/^\*\*(致|发件人|主题)[:：]\*\*.*?\n/gm, "")
    .replace(/^\*\*(致|发件人|主题)[:：].*?\*\*\s*.*?\n/gm, "")
    .replace(/^尊敬的.*?团队[，,：:]?\s*/, "")
    .trim();
}

function renderAdvisorText(value: string): string {
  const lines = cleanAdvisorText(value)
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?[^>]+>/g, "")
    .split("\n")
    .map((line) => line.trim());
  const parts: string[] = [];
  let listItems: string[] = [];

  const flushList = () => {
    if (listItems.length) {
      parts.push(`<ul>${listItems.join("")}</ul>`);
      listItems = [];
    }
  };

  for (const line of lines) {
    if (!line || line === "---" || line.startsWith("```")) {
      flushList();
      continue;
    }
    const heading = line.match(/^#{1,6}\s*(.+)$/);
    if (heading) {
      flushList();
      const title = heading[1].replace(/^\*\*|\*\*$/g, "").trim();
      if (title.includes("诊断补充建议报告") || title.includes("管理摘要")) continue;
      parts.push(`<h4>${inlineMarkdown(title)}</h4>`);
      continue;
    }
    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      listItems.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      continue;
    }
    parts.push(`<p>${inlineMarkdown(line)}</p>`);
  }
  flushList();
  return parts.join("");
}

function normalizeReportHtml(value: string): string {
  return value.replace(/<div class="report-ai-text">([\s\S]*?)<\/div>/g, (match, content: string) => {
    if (/<(?:h4|p|ul|ol|li)\b/i.test(content)) return match;
    return `<div class="report-ai-text">${renderAdvisorText(content)}</div>`;
  });
}

function formatDate(iso: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

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

async function createCase() {
  const created = await api.createCase({ ...caseForm });
  cases.value = [created, ...cases.value];
  caseForm.title = "";
  caseForm.function_area = "";
  caseForm.description = "";
  caseForm.expected_benefit = "";
}

async function createChannel() {
  error.value = "";
  adminNotice.value = "";
  try {
    const created = await api.createChannel({ ...channelForm, is_active: true });
    const index = channels.value.findIndex((item) => item.id === created.id);
    channels.value = index >= 0
      ? channels.value.map((item) => item.id === created.id ? created : item)
      : [...channels.value, created];
    channelForm.code = "";
    channelForm.name = "";
    channelForm.description = "";
    adminNotice.value = "渠道二维码已生成";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "渠道创建失败";
  }
}

async function createUser() {
  error.value = "";
  adminNotice.value = "";
  try {
    const created = await api.createUser({ ...userForm });
    users.value = [...users.value, created];
    userForm.email = "";
    userForm.name = "";
    userForm.password = "";
    adminNotice.value = "账号已创建，可使用邮箱和初始密码登录";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "账号创建失败";
  }
}

async function deleteChannel(item: ChannelSource) {
  if (!window.confirm(`确定删除“${item.name}”的二维码吗？删除后链接将立即失效。`)) return;
  error.value = "";
  adminNotice.value = "";
  try {
    await api.deleteChannel(item.id);
    channels.value = channels.value.filter((channel) => channel.id !== item.id);
    adminNotice.value = "渠道二维码已删除";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "删除二维码失败";
  }
}

function handleBeforeUnload() {
  if (step.value === "info" || step.value === "questionnaire") {
    persistLeadForm();
    persistStep();
    localStorage.setItem("diagnosis_module_index", String(moduleIndex.value));
  }
  if (step.value === "questionnaire" && submissionId.value && Object.keys(answers.value).length > 0) {
    localStorage.setItem("diagnosis_answers", JSON.stringify(answers.value));
  }
}

watch(
  leadForm,
  () => {
    if (step.value === "info" || step.value === "questionnaire") {
      persistLeadForm();
    }
  },
  { deep: true },
);

watch([selectedAiFocus, aiFocusOther], syncAiFocus, { deep: true });

watch(moduleIndex, (value: number) => {
  localStorage.setItem("diagnosis_module_index", String(value));
});

watch([leadSortOrder, leadStrategyFilter, leadIndustryFilter, leadPageSize], resetLeadPage);

watch(leadTotalPages, (totalPages) => {
  if (leadPage.value > totalPages) {
    leadPage.value = totalPages;
  }
});

onMounted(async () => {
  window.addEventListener("beforeunload", handleBeforeUnload);
  try {
    if (isAdmin && adminToken.value) {
      await loadAdminShell();
    } else if (reportToken) {
      await loadPublicReport();
    } else if (!isAdmin) {
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
      <button class="secondary" @click="logoutAdmin"><LogOut :size="18" /> 退出</button>
    </aside>
    <section class="admin-main">
      <nav class="tabs">
        <button v-for="tab in adminTabs" :key="tab.key" :class="{ active: adminTab === tab.key }" @click="loadAdminTab(tab.key)">
          <component :is="tab.icon" :size="17" /> {{ tab.label }}
        </button>
      </nav>
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

          <section class="analytics-card distribution-card">
            <header><h2>打法分布</h2></header>
            <div class="rank-list">
              <div v-for="item in analytics.strategy_distribution" :key="item.label">
                <span>{{ item.label }}</span>
                <div><i :style="{ width: bucketPct(item.count, analytics.strategy_distribution) }"></i></div>
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

      <section v-if="adminTab === 'leads'" class="table-section">
        <div class="table-actions">
          <h2>线索列表</h2>
          <div class="table-action-buttons">
            <button class="secondary" type="button" @click="leadRuleDialogOpen = true"><BookOpen :size="18" /> 评分规则</button>
            <a class="secondary link-button" href="/api/admin/leads/export"><ArrowDownToLine :size="18" /> 导出</a>
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
            打法
            <select v-model="leadStrategyFilter">
              <option v-for="item in leadStrategyOptions" :key="item">{{ item }}</option>
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
            <thead><tr><th>公司</th><th>行业</th><th>联系人</th><th>职位</th><th>联系</th><th>等级</th><th>打法</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="lead in pagedLeads" :key="lead.id" class="clickable-row" tabindex="0" @click="openLeadDetail(lead)" @keydown.enter="openLeadDetail(lead)">
                <td :title="lead.company_name || ''">{{ lead.company_name }}</td>
                <td :title="lead.industry || ''">{{ lead.industry }}</td>
                <td :title="lead.contact_name || ''">{{ lead.contact_name }}</td>
                <td :title="lead.position || ''">{{ lead.position }}</td>
                <td :title="lead.phone || lead.wechat || ''">{{ lead.phone || lead.wechat }}</td>
                <td><span class="pill" :class="lead.lead_level">{{ lead.lead_level }}</span></td>
                <td><span class="pill strategy">{{ lead.priority_strategy || "未判定" }}</span></td>
                <td>{{ new Date(lead.created_at).toLocaleString() }}</td>
              </tr>
              <tr v-if="!pagedLeads.length">
                <td colspan="8" class="empty-cell">暂无符合条件的线索</td>
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

      <div v-if="adminTab === 'questions'" class="module-list">
        <section v-for="module in adminQuestions" :key="module.id" class="module-block">
          <h2>{{ module.sort_order }}. {{ module.name }}<span>{{ module.max_score }}分</span></h2>
          <p v-for="question in module.questions" :key="question.id">{{ question.code }} · {{ question.text }}</p>
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
        <button class="hero-pdf-btn" type="button" @click="openEmailDialog">
          <Mail :size="18" /> 发送到邮箱
        </button>
      </header>
      <div v-if="emailNotice" class="success-alert">{{ emailNotice }}</div>

      <!-- Score Cards -->
      <div v-if="reportScore" class="score-strip">
        <div class="score-card score-card--total">
          <span class="score-card-label">诊断总分</span>
          <strong>{{ reportScore.total }}<em>/{{ reportScore.max }}</em></strong>
          <div class="score-card-bar"><span :style="{ width: `${Math.round(reportScore.rate * 100)}%` }"></span></div>
        </div>
        <div class="score-card score-card--level">
          <span class="score-card-label">就绪度等级</span>
          <strong class="level-{{ reportScore.level }}">{{ reportScore.level }}</strong>
          <span class="score-card-sub">AI 原生转型就绪度评估</span>
        </div>
        <div class="score-card score-card--rate">
          <span class="score-card-label">综合得分率</span>
          <strong>{{ Math.round(reportScore.rate * 100) }}<em>%</em></strong>
          <div class="score-card-ring">
            <svg viewBox="0 0 36 36"><path class="ring-bg" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/><path class="ring-fill" :stroke-dasharray="`${Math.round(reportScore.rate * 100)}, 100`" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/></svg>
          </div>
        </div>
      </div>

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
        <label>
          接收报告邮箱
          <input v-model="leadForm.email" type="email" required placeholder="name@example.com" />
          <span class="field-hint">请填写真实可收信邮箱，完整诊断报告和生成文件会发送到这里。</span>
        </label>
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
          <button class="hero-pdf-btn" type="button" @click="openEmailDialog">
            <Mail :size="18" /> 发送到邮箱
          </button>
        </header>
        <div v-if="emailNotice" class="success-alert">{{ emailNotice }}</div>

        <!-- Score Cards -->
        <div v-if="reportScore" class="score-strip">
          <div class="score-card score-card--total">
            <span class="score-card-label">诊断总分</span>
            <strong>{{ reportScore.total }}<em>/{{ reportScore.max }}</em></strong>
            <div class="score-card-bar"><span :style="{ width: `${Math.round(reportScore.rate * 100)}%` }"></span></div>
          </div>
          <div class="score-card score-card--level">
            <span class="score-card-label">就绪度等级</span>
            <strong class="level-{{ reportScore.level }}">{{ reportScore.level }}</strong>
            <span class="score-card-sub">AI 原生转型就绪度评估</span>
          </div>
          <div class="score-card score-card--rate">
            <span class="score-card-label">综合得分率</span>
            <strong>{{ Math.round(reportScore.rate * 100) }}<em>%</em></strong>
            <div class="score-card-ring">
              <svg viewBox="0 0 36 36"><path class="ring-bg" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/><path class="ring-fill" :stroke-dasharray="`${Math.round(reportScore.rate * 100)}, 100`" d="M18 2a16 16 0 1 1 0 32 16 16 0 0 1 0-32"/></svg>
            </div>
          </div>
        </div>

        <!-- Charts -->
        <ReportCharts :dimensions="chartDimensions" />

        <!-- Report Content -->
        <article class="report-html" v-html="reportHtml" />
      </section>
    </section>
  </main>

  <div v-if="emailDialogOpen" class="modal-backdrop" @click.self="emailDialogOpen = false">
    <form class="email-dialog" @submit.prevent="sendReportToEmail">
      <h2>发送完整报告</h2>
      <p>请输入接收邮箱，系统会将 PDF 报告发送到该邮箱。</p>
      <label>邮箱地址<input v-model="reportEmail" type="email" required placeholder="name@example.com" /></label>
      <div class="dialog-actions">
        <button type="button" class="secondary" @click="emailDialogOpen = false">取消</button>
        <button class="primary" :disabled="emailSending">{{ emailSending ? "发送中..." : "发送报告" }}</button>
      </div>
    </form>
  </div>

  <div v-if="leadDetailOpen" class="modal-backdrop" @click.self="leadDetailOpen = false">
    <section class="lead-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="lead-detail-title">
      <header>
        <div>
          <p class="eyebrow">客户详情</p>
          <h2 id="lead-detail-title">{{ selectedLeadDetail?.lead.company_name || "客户详情" }}</h2>
        </div>
        <button class="secondary" type="button" @click="leadDetailOpen = false">关闭</button>
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
            <div><span>来源</span><strong>{{ selectedLeadDetail.lead.source_code || "-" }}</strong></div>
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
            <div><span>建议打法</span><strong><span class="pill strategy">{{ selectedLeadDetail.lead.priority_strategy || "未判定" }}</span></strong></div>
            <div><span>总分</span><strong>{{ selectedLeadDetail.submission?.total_score ?? "-" }}/{{ selectedLeadDetail.submission?.max_score ?? 260 }}</strong></div>
            <div><span>得分率</span><strong>{{ selectedLeadScoreRate }}</strong></div>
            <div><span>风险等级</span><strong>{{ selectedLeadDetail.submission?.risk_level || "-" }}</strong></div>
            <div><span>提交时间</span><strong>{{ selectedLeadDetail.submission?.submitted_at ? new Date(selectedLeadDetail.submission.submitted_at).toLocaleString() : "-" }}</strong></div>
          </div>
          <div v-if="selectedLeadDetail.submission?.dimensions?.length" class="dimension-mini-list">
            <div v-for="item in selectedLeadDetail.submission.dimensions" :key="item.module_code">
              <span>{{ item.module_name }}</span>
              <b>{{ Math.round(item.score_rate * 100) }}%</b>
              <em>{{ item.risk_level }}</em>
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

      <div class="rule-block">
        <h3>打法：建议跟进方式</h3>
        <ul>
          <li><strong>升维战：</strong>综合得分率大于等于 75%。说明企业基础较好，适合做跨部门规模化、经营升级类 AI 项目。</li>
          <li><strong>攻坚战：</strong>综合得分率低于 50%，或低分维度数量大于等于 4 个。说明基础短板较多，需要先补业务、流程、数据或组织基础。</li>
          <li><strong>闪电战：</strong>综合得分没有明显偏低，并且客户填写了明确 AI 诉求。适合先从一个小场景快速试点，比如客服提效、流程自动化、知识库问答。</li>
          <li><strong>默认攻坚战：</strong>如果不满足以上条件，系统默认按攻坚战处理，避免过早承诺快速落地。</li>
        </ul>
      </div>

      <p class="rule-note">当前规则是首版自动判定逻辑，后续可以继续加入企业规模、年营收、行业权重、职位角色等因素，让线索优先级更贴近真实销售判断。</p>
    </section>
  </div>

</template>

/** 后台管理 — 登录态、统计看板、线索、题库、案例、账号与渠道。 */

import { computed, reactive, ref, watch, type Component } from "vue";
import { BookOpen, BriefcaseBusiness, FileText, LayoutDashboard, QrCode, Users } from "lucide-vue-next";

import { ApiError, api } from "../api";
import type { AnalyticsSummary, CaseStudy, ChannelSource, Lead, LeadDetail, Question, QuestionModule, User } from "../types";
import { formatDateTime, isValidEmail, parseApiDate } from "../utils/format";
import { normalizeReportHtml } from "../utils/reportHtml";
import { adminNotice, error } from "./feedback";

export type AdminTab = "overview" | "leads" | "questions" | "cases" | "users" | "channels";
type LeadSortOrder = "newest" | "oldest";

export function useAdmin() {
  const adminToken = ref(false);
  const adminUser = ref<User | null>(null);
  const adminEmail = ref("admin@example.com");
  const adminPassword = ref("");
  const adminTab = ref<AdminTab>("overview");
  const analytics = ref<AnalyticsSummary | null>(null);
  const leads = ref<Lead[]>([]);
  const leadSortOrder = ref<LeadSortOrder>("newest");
  const leadIndustryFilter = ref("全部行业");
  const leadPageSize = ref(10);
  const leadPage = ref(1);
  const leadRuleDialogOpen = ref(false);
  const leadDetailOpen = ref(false);
  const leadDetailLoading = ref(false);
  const selectedLeadDetail = ref<LeadDetail | null>(null);
  const diagnosticEmailDraft = ref("");
  const diagnosticEmailUpdating = ref(false);
  const adminQuestions = ref<QuestionModule[]>([]);
  const questionBankDialog = ref<"module" | "question" | null>(null);
  const questionBankSaving = ref(false);
  const cases = ref<CaseStudy[]>([]);
  const users = ref<User[]>([]);
  const channels = ref<ChannelSource[]>([]);
  const leadsExporting = ref(false);
  const leadWordExporting = ref(false);

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

  const channelForm = reactive({ code: "", name: "", description: "" });

  const adminTabs: { key: AdminTab; label: string; icon: Component }[] = [
    { key: "overview", label: "统计", icon: LayoutDashboard },
    { key: "leads", label: "线索", icon: BriefcaseBusiness },
    { key: "questions", label: "题库", icon: BookOpen },
    { key: "cases", label: "案例", icon: FileText },
    { key: "users", label: "账号", icon: Users },
    { key: "channels", label: "渠道", icon: QrCode }
  ];

  function clearAdminSession(message = "") {
    adminToken.value = false;
    adminUser.value = null;
    analytics.value = null;
    leads.value = [];
    adminQuestions.value = [];
    cases.value = [];
    users.value = [];
    channels.value = [];
    if (message) error.value = message;
  }

  function handleAdminRequestError(err: unknown): boolean {
    if (err instanceof ApiError && err.status === 401) {
      void api.logout().catch(() => undefined);
      clearAdminSession("登录状态已失效，请重新登录。");
      return true;
    }
    return false;
  }

  async function loginAdmin() {
    error.value = "";
    try {
      await api.login(adminEmail.value, adminPassword.value);
      adminToken.value = true;
      await loadAdminShell();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "登录失败";
    }
  }

  async function loadAdminShell() {
    try {
      adminUser.value = await api.me();
      adminToken.value = true;
      await loadAdminTab("overview");
    } catch (err) {
      if (!handleAdminRequestError(err)) {
        error.value = err instanceof Error ? err.message : "加载后台失败";
      }
    }
  }

  async function loadAdminTab(tab: AdminTab) {
    try {
      if (tab !== "leads") closeLeadDetail();
      adminTab.value = tab;
      if (tab === "overview") analytics.value = await api.analytics();
      if (tab === "leads") {
        const [leadRows, channelRows] = await Promise.all([api.leads(), api.channels().catch(() => [])]);
        leads.value = leadRows;
        channels.value = channelRows;
        resetLeadPage();
      }
      if (tab === "questions") adminQuestions.value = await api.adminQuestions();
      if (tab === "cases") cases.value = await api.cases();
      if (tab === "users") users.value = await api.users().catch(() => []);
      if (tab === "channels") channels.value = await api.channels().catch(() => []);
    } catch (err) {
      if (!handleAdminRequestError(err)) {
        error.value = err instanceof Error ? err.message : "加载后台数据失败";
      }
    }
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
      diagnosticEmailDraft.value = selectedLeadDetail.value.lead.email || "";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载客户详情失败";
      leadDetailOpen.value = false;
    } finally {
      leadDetailLoading.value = false;
    }
  }

  function closeLeadDetail() {
    leadDetailOpen.value = false;
    selectedLeadDetail.value = null;
    diagnosticEmailDraft.value = "";
  }

  async function updateLeadDiagnosticEmail() {
    const detail = selectedLeadDetail.value;
    const email = diagnosticEmailDraft.value.trim();
    if (!detail) return;
    if (!isValidEmail(email)) {
      error.value = "请输入正确的诊断邮箱地址";
      return;
    }
    diagnosticEmailUpdating.value = true;
    error.value = "";
    try {
      const result = await api.updateLeadDiagnosticEmail(detail.lead.id, email);
      adminNotice.value = result.message;
      selectedLeadDetail.value = await api.leadDetail(detail.lead.id);
      diagnosticEmailDraft.value = selectedLeadDetail.value.lead.email || email;
      await loadAdminTab("leads");
    } catch (err) {
      error.value = err instanceof Error ? err.message : "更正诊断邮箱失败";
    } finally {
      diagnosticEmailUpdating.value = false;
    }
  }

  async function exportLeads() {
    leadsExporting.value = true;
    error.value = "";
    try {
      await api.leadsExport();
      adminNotice.value = "线索列表已导出";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "导出线索失败";
    } finally {
      leadsExporting.value = false;
    }
  }

  async function exportLeadWord() {
    const detail = selectedLeadDetail.value;
    if (!detail) return;
    leadWordExporting.value = true;
    error.value = "";
    try {
      await api.leadWordExport(detail.lead.id);
      adminNotice.value = "客户档案已导出";
    } catch (err) {
      error.value = err instanceof Error ? err.message : "导出客户档案失败";
    } finally {
      leadWordExporting.value = false;
    }
  }

  async function logoutAdmin() {
    await api.logout().catch(() => undefined);
    clearAdminSession();
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

  const questionModuleForm = reactive({
    name: "",
    description: "",
    max_score: 28,
    sort_order: 1
  });

  const questionForm = reactive({
    module_code: "",
    code: "",
    dimension: "",
    text: "",
    option_text: "0=完全不符合；1=较不符合；2=部分符合；3=基本符合；4=完全符合",
    sort_order: 1,
    max_score: 4
  });

  function nextQuestionModuleCode() {
    const highest = Math.max(0, ...adminQuestions.value.map((module) => Number(module.code.match(/^M(\d+)$/)?.[1]) || 0));
    return `M${String(highest + 1).padStart(2, "0")}`;
  }

  function nextQuestionCode() {
    const highest = Math.max(0, ...adminQuestions.value.flatMap((module) => module.questions).map((question) => Number(question.code.match(/^Q(\d+)$/)?.[1]) || 0));
    return `Q${highest + 1}`;
  }

  function openQuestionModuleDialog() {
    questionModuleForm.name = "";
    questionModuleForm.description = "";
    questionModuleForm.max_score = 28;
    questionModuleForm.sort_order = Math.max(0, ...adminQuestions.value.map((module) => module.sort_order)) + 1;
    questionBankDialog.value = "module";
  }

  function openQuestionDialog(module: QuestionModule) {
    questionForm.module_code = module.code;
    questionForm.code = nextQuestionCode();
    questionForm.dimension = module.name;
    questionForm.text = "";
    questionForm.option_text = "0=完全不符合；1=较不符合；2=部分符合；3=基本符合；4=完全符合";
    questionForm.sort_order = Math.max(0, ...module.questions.map((question) => question.sort_order)) + 1;
    questionForm.max_score = 4;
    questionBankDialog.value = "question";
  }

  async function createQuestionModule() {
    questionBankSaving.value = true;
    error.value = "";
    try {
      await api.createQuestionModule({
        code: nextQuestionModuleCode(),
        name: questionModuleForm.name.trim(),
        description: questionModuleForm.description.trim() || null,
        max_score: questionModuleForm.max_score,
        sort_order: questionModuleForm.sort_order,
        is_active: true
      });
      questionBankDialog.value = null;
      adminNotice.value = "题库已新增";
      await loadAdminTab("questions");
    } catch (err) {
      error.value = err instanceof Error ? err.message : "新增题库失败";
    } finally {
      questionBankSaving.value = false;
    }
  }

  async function createQuestion() {
    questionBankSaving.value = true;
    error.value = "";
    try {
      await api.createQuestion({
        ...questionForm,
        dimension: questionForm.dimension.trim() || null,
        text: questionForm.text.trim(),
        option_text: questionForm.option_text.trim() || null,
        is_active: true
      });
      questionBankDialog.value = null;
      adminNotice.value = "题目已新增";
      await loadAdminTab("questions");
    } catch (err) {
      error.value = err instanceof Error ? err.message : "新增题目失败";
    } finally {
      questionBankSaving.value = false;
    }
  }

  async function deleteQuestionModule(module: QuestionModule) {
    if (!window.confirm(`确定删除题库“${module.name}”吗？新客户将不再看到其中题目，历史报告不会受影响。`)) return;
    error.value = "";
    try {
      const result = await api.deleteQuestionModule(module.id);
      adminNotice.value = result.message;
      await loadAdminTab("questions");
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除题库失败";
    }
  }

  async function deleteQuestion(question: Question) {
    if (!window.confirm(`确定删除“${question.code}”吗？新客户将不再看到此题，历史报告不会受影响。`)) return;
    error.value = "";
    try {
      const result = await api.deleteQuestion(question.id);
      adminNotice.value = result.message;
      await loadAdminTab("questions");
    } catch (err) {
      error.value = err instanceof Error ? err.message : "删除题目失败";
    }
  }

  const canExportLeads = computed(() => ["admin", "operator", "sales"].includes(adminUser.value?.role || ""));
  const canManageQuestionBank = computed(() => ["admin", "operator"].includes(adminUser.value?.role || ""));
  const leadIndustryOptions = computed(() => ["全部行业", ...Array.from(new Set(leads.value.map((lead) => lead.industry || "未填写").filter(Boolean)))]);

  function sourceLabel(code: string | null | undefined): string {
    if (!code) return "未标记来源";
    return channels.value.find((channel) => channel.code === code)?.name || code;
  }

  const filteredLeads = computed(() => {
    return leads.value
      .filter((lead) => leadIndustryFilter.value === "全部行业" || (lead.industry || "未填写") === leadIndustryFilter.value)
      .sort((a, b) => {
        const bTime = b.last_activity_at || b.updated_at || b.created_at;
        const aTime = a.last_activity_at || a.updated_at || a.created_at;
        const diff = parseApiDate(bTime).getTime() - parseApiDate(aTime).getTime();
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

  const leadDetailReportHtml = computed(() => normalizeReportHtml(selectedLeadDetail.value?.report?.html_content || ""));
  const selectedLeadScoreRate = computed(() => {
    const rate = selectedLeadDetail.value?.submission?.score_rate;
    return rate === null || rate === undefined ? "-" : `${Math.round(rate * 100)}%`;
  });

  watch([leadSortOrder, leadIndustryFilter, leadPageSize], resetLeadPage);

  watch(leadTotalPages, (totalPages) => {
    if (leadPage.value > totalPages) {
      leadPage.value = totalPages;
    }
  });

  return {
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
    resetLeadPage,
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
  };
}

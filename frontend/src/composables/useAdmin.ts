/** 后台管理 — 登录态、统计看板、线索、题库、案例、账号与渠道。 */

import { computed, reactive, ref, watch, type Component } from "vue";
import { BookOpen, BriefcaseBusiness, FileText, KeyRound, LayoutDashboard, QrCode, Users } from "lucide-vue-next";

import { ApiError, api, type LeadQueryParams } from "../api";
import type { AnalyticsSummary, CaseStudy, ChannelSource, CompanyResearch, CompanyResearchValue, ExportBatch, GatewayConfig, Lead, LeadDetail, Question, QuestionModule, User } from "../types";
import { isValidEmail } from "../utils/format";
import { normalizeReportHtml } from "../utils/reportHtml";
import { clearToasts, pushToast } from "./feedback";

export type AdminTab = "overview" | "leads" | "questions" | "cases" | "users" | "channels" | "gateway";
type LeadSortOrder = "newest" | "oldest";

type CompanyResearchSectionKey =
  | "company_overview"
  | "revenue_scale"
  | "products"
  | "industry_characteristics"
  | "development_status"
  | "challenges"
  | "ai_opportunities";

export const companyResearchSections: [CompanyResearchSectionKey, string][] = [
  ["company_overview", "公司介绍"],
  ["revenue_scale", "营收规模"],
  ["products", "产品"],
  ["industry_characteristics", "行业特点"],
  ["development_status", "发展现状"],
  ["challenges", "可能遇到的挑战"],
  ["ai_opportunities", "AI 能帮他们做什么"],
];

export function researchSubsections(value: CompanyResearchValue | undefined) {
  if (!Array.isArray(value)) return [];
  return value.filter((item) => item && typeof item.title === "string" && typeof item.content === "string");
}

export function researchLegacyText(value: CompanyResearchValue | undefined) {
  return typeof value === "string" ? value.trim() : "";
}

/** 内置搜索服务商的官方固定地址（不可自定义）。 */
export const searchProviderOfficialUrls: Record<string, string> = {
  bocha: "https://api.bochaai.com/v1",
  serpapi: "https://serpapi.com",
  deepseek: "https://api.deepseek.com",
};

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
  const leadCreatedFrom = ref("");
  const leadCreatedTo = ref("");
  const leadLevelFilter = ref("");
  const leadViewFilter = ref("");
  const leadProcessingFilter = ref("");
  const leadExportFilter = ref("");
  const leadIndustrySource = ref<Lead[]>([]); // 未筛选全量列表，仅用于构建行业下拉选项
  const leadPageSize = ref(10);
  const leadPage = ref(1);
  const leadRuleDialogOpen = ref(false);
  const leadDetailOpen = ref(false);
  const leadDetailLoading = ref(false);
  const selectedLeadDetail = ref<LeadDetail | null>(null);
  const researchRunning = ref(false);
  const resumeDeliveryRunning = ref(false);
  let researchPollTimer: number | null = null;
  const diagnosticEmailDraft = ref("");
  const diagnosticEmailUpdating = ref(false);
  const adminQuestions = ref<QuestionModule[]>([]);
  const questionBankDialog = ref<"module" | "question" | null>(null);
  const questionBankSaving = ref(false);
  const cases = ref<CaseStudy[]>([]);
  const users = ref<User[]>([]);
  const channels = ref<ChannelSource[]>([]);
  const leadsExporting = ref(false);
  const leadsBatchExporting = ref(false);
  const exportBatches = ref<ExportBatch[]>([]);
  const exportBatchPanelOpen = ref(false);
  const batchDownloading = ref<number | null>(null);
  const leadWordExporting = ref(false);
  const gatewayConfig = ref<GatewayConfig | null>(null);
  const searchSaving = ref(false);
  const searchTesting = ref(false);
  const llmSaving = ref(false);
  const llmTesting = ref(false);
  const searchForm = reactive({
    search_provider: "deepseek" as "bocha" | "serpapi" | "deepseek" | "custom",
    search_api_key: "",
    search_base_url: "",
    search_timeout_seconds: 15,
    search_max_results: 20,
    search_model: ""
  });
  const llmForm = reactive({
    llm_api_key: "",
    llm_base_url: "",
    llm_model: ""
  });

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
    { key: "channels", label: "渠道", icon: QrCode },
    { key: "gateway", label: "API 配置", icon: KeyRound }
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
    if (message) pushToast("severe", message);
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
    try {
      await api.login(adminEmail.value, adminPassword.value);
      adminToken.value = true;
      await loadAdminShell();
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "登录失败");
    }
  }

  async function loadAdminShell() {
    try {
      adminUser.value = await api.me();
      adminToken.value = true;
      await loadAdminTab("overview");
    } catch (err) {
      if (!handleAdminRequestError(err)) {
        pushToast("error", err instanceof Error ? err.message : "加载后台失败");
      }
    }
  }

  async function loadAdminTab(tab: AdminTab) {
    // 页面切换时清理旧提示；同页签内部刷新（如删除线索后重载）保留刚产生的提示。
    const tabChanged = adminTab.value !== tab;
    if (tabChanged) clearToasts();
    try {
      if (tab !== "leads") closeLeadDetail();
      adminTab.value = tab;
      if (tab === "overview") analytics.value = await api.analytics();
      if (tab === "leads") {
        const [leadRows, industryRows, channelRows] = await Promise.all([
          api.leads(leadQueryParams()),
          api.leads({}).catch(() => [] as Lead[]),
          api.channels().catch(() => []),
        ]);
        leads.value = leadRows;
        leadIndustrySource.value = industryRows;
        channels.value = channelRows;
        resetLeadPage();
      }
      if (tab === "questions") adminQuestions.value = await api.adminQuestions();
      if (tab === "cases") cases.value = await api.cases();
      if (tab === "users") users.value = await api.users().catch(() => []);
      if (tab === "channels") channels.value = await api.channels().catch(() => []);
      if (tab === "gateway") await loadGatewayTab();
    } catch (err) {
      if (!handleAdminRequestError(err)) {
        pushToast("error", err instanceof Error ? err.message : "加载后台数据失败");
      }
    }
  }

  /** 当前筛选条件 → 后端查询参数（列表/导出共用）。 */
  function leadQueryParams(): LeadQueryParams {
    return {
      industry: leadIndustryFilter.value === "全部行业" ? "" : leadIndustryFilter.value,
      lead_level: leadLevelFilter.value,
      created_from: leadCreatedFrom.value,
      created_to: leadCreatedTo.value,
      view_status: leadViewFilter.value,
      processing_status: leadProcessingFilter.value,
      export_status: leadExportFilter.value,
      sort: leadSortOrder.value,
    };
  }

  /** 按当前筛选条件从服务端重新拉取线索列表（排序由后端完成）。 */
  async function loadLeads() {
    try {
      leads.value = await api.leads(leadQueryParams());
      resetLeadPage();
    } catch (err) {
      if (!handleAdminRequestError(err)) {
        pushToast("error", err instanceof Error ? err.message : "加载线索失败");
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
    try {
      selectedLeadDetail.value = await api.leadDetail(lead.id);
      diagnosticEmailDraft.value = selectedLeadDetail.value.lead.email || "";
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "加载客户详情失败");
      leadDetailOpen.value = false;
    } finally {
      leadDetailLoading.value = false;
    }
  }

  /** 严重提示的「查看客户」入口：按 id 直达详情（列表中可能已被筛选排除）。 */
  function openLeadDetailById(leadId: number) {
    const lead = leads.value.find((item) => item.id === leadId) || ({ id: leadId } as Lead);
    void openLeadDetail(lead);
  }

  function closeLeadDetail() {
    leadDetailOpen.value = false;
    selectedLeadDetail.value = null;
    diagnosticEmailDraft.value = "";
    clearResearchPolling();
    researchRunning.value = false;
    clearToasts();
  }

  function clearResearchPolling() {
    if (researchPollTimer !== null) {
      window.clearInterval(researchPollTimer);
      researchPollTimer = null;
    }
  }

  async function runLeadResearch() {
    const detail = selectedLeadDetail.value;
    if (!detail || researchRunning.value) return;
    researchRunning.value = true;
    try {
      const force = Boolean(detail.report?.company_research);
      const result = await api.triggerLeadResearch(detail.lead.id, force);
      pushToast("success", result.message || "已开始检索");
      if (result.status === "already_generated") {
        selectedLeadDetail.value = await api.leadDetail(detail.lead.id);
        researchRunning.value = false;
        return;
      }
      // 后台任务异步执行，轮询刷新直到情报出现或超时（最长 3 分钟）
      let attempts = 0;
      researchPollTimer = window.setInterval(async () => {
        attempts += 1;
        try {
          const refreshed = await api.leadDetail(detail.lead.id);
          selectedLeadDetail.value = refreshed;
          const researchStatus = refreshed.report?.research_status;
          if (["generated", "failed", "review"].includes(researchStatus || "") || attempts >= 60) {
            clearResearchPolling();
            researchRunning.value = false;
            if (researchStatus === "generated" && refreshed.report?.company_research) {
              // 情报已生成，但报告/投递任务此前失败时提示继续生成，而不是显示流程已完成
              const blocked =
                refreshed.report.status === "failed" ||
                refreshed.delivery?.status === "failed" ||
                !refreshed.delivery;
              if (blocked) {
                pushToast("severe", "企业情报已生成，但 AI 报告/邮件投递任务此前失败：请点击「继续生成报告并发送」完成后续流程", {
                  leadId: detail.lead.id,
                  leadName: detail.lead.company_name,
                });
              } else {
                pushToast("success", "企业情报与 AI 分析已生成");
              }
            } else {
              pushToast("severe", "检索未生成结果：可能公司名称过短或公开信息不足，可稍后重试", {
                leadId: detail.lead.id,
                leadName: detail.lead.company_name,
              });
            }
          }
        } catch (err) {
          clearResearchPolling();
          researchRunning.value = false;
          pushToast("error", err instanceof Error ? err.message : "刷新检索结果失败");
        }
      }, 3000);
    } catch (err) {
      researchRunning.value = false;
      pushToast("error", err instanceof Error ? err.message : "触发检索失败");
    }
  }

  async function resumeReportDelivery() {
    const detail = selectedLeadDetail.value;
    if (!detail || resumeDeliveryRunning.value) return;
    resumeDeliveryRunning.value = true;
    try {
      const result = await api.resumeReportDelivery(detail.lead.id);
      pushToast("success", result.message || "已继续生成报告并发送");
      await new Promise((resolve) => setTimeout(resolve, 800));
      selectedLeadDetail.value = await api.leadDetail(detail.lead.id);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "继续生成报告失败");
    } finally {
      resumeDeliveryRunning.value = false;
    }
  }

  async function updateLeadDiagnosticEmail() {
    const detail = selectedLeadDetail.value;
    const email = diagnosticEmailDraft.value.trim();
    if (!detail) return;
    if (!isValidEmail(email)) {
      pushToast("error", "请输入正确的诊断邮箱地址");
      return;
    }
    diagnosticEmailUpdating.value = true;
    try {
      const result = await api.updateLeadDiagnosticEmail(detail.lead.id, email);
      pushToast("success", result.message);
      selectedLeadDetail.value = await api.leadDetail(detail.lead.id);
      diagnosticEmailDraft.value = selectedLeadDetail.value.lead.email || email;
      await loadAdminTab("leads");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "更正诊断邮箱失败");
    } finally {
      diagnosticEmailUpdating.value = false;
    }
  }

  async function exportLeads() {
    leadsExporting.value = true;
    try {
      await api.leadsExport(leadQueryParams());
      pushToast("success", "线索已按当前筛选条件导出");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "导出线索失败");
    } finally {
      leadsExporting.value = false;
    }
  }

  /** 一键导出全部未导出客户：成功后自动下载批次文件并刷新列表导出状态。 */
  async function exportUnexported() {
    if (leadsBatchExporting.value) return;
    leadsBatchExporting.value = true;
    try {
      const result = await api.exportUnexportedLeads();
      pushToast("success", result.message);
      if (result.batch_id !== null) {
        await api.downloadExportBatch(result.batch_id);
        await loadLeadBatches();
        await loadLeads();
      }
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "一键导出失败");
    } finally {
      leadsBatchExporting.value = false;
    }
  }

  async function loadLeadBatches() {
    try {
      exportBatches.value = await api.exportBatches();
    } catch {
      // 批次历史加载失败不打断主流程
    }
  }

  function toggleExportBatches() {
    exportBatchPanelOpen.value = !exportBatchPanelOpen.value;
    if (exportBatchPanelOpen.value) void loadLeadBatches();
  }

  async function downloadBatch(batch: ExportBatch) {
    if (batchDownloading.value !== null) return;
    batchDownloading.value = batch.id;
    try {
      await api.downloadExportBatch(batch.id);
      pushToast("success", `批次 #${batch.id}（${batch.rows_count} 位客户）已重新下载`);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "重新下载批次失败");
    } finally {
      batchDownloading.value = null;
    }
  }

  async function exportLeadWord() {
    const detail = selectedLeadDetail.value;
    if (!detail) return;
    leadWordExporting.value = true;
    try {
      await api.leadWordExport(detail.lead.id);
      pushToast("success", "客户档案已导出");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "导出客户档案失败");
    } finally {
      leadWordExporting.value = false;
    }
  }

  async function deleteLead(lead: Lead | { id: number; company_name?: string | null }) {
    const name = "company_name" in lead && lead.company_name ? `「${lead.company_name}」` : `#${lead.id}`;
    if (!window.confirm(`确定删除线索 ${name} 吗？\n将同时删除该客户的企业信息、全部答题、评分与诊断报告，且无法恢复。删除后该客户可重新填写。`)) return;
    const leadId = lead.id;
    const wasDetailOpen = selectedLeadDetail.value?.lead.id === leadId;
    try {
      const result = await api.deleteLead(leadId);
      if (wasDetailOpen) closeLeadDetail();
      pushToast("success", result.message);
      await loadAdminTab("leads");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "删除线索失败");
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
    try {
      const created = await api.createChannel({ ...channelForm, is_active: true });
      const index = channels.value.findIndex((item) => item.id === created.id);
      channels.value = index >= 0
        ? channels.value.map((item) => item.id === created.id ? created : item)
        : [...channels.value, created];
      channelForm.code = "";
      channelForm.name = "";
      channelForm.description = "";
      pushToast("success", "渠道二维码已生成");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "渠道创建失败");
    }
  }

  async function createUser() {
    try {
      const created = await api.createUser({ ...userForm });
      users.value = [...users.value, created];
      userForm.email = "";
      userForm.name = "";
      userForm.password = "";
      pushToast("success", "账号已创建，可使用邮箱和初始密码登录");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "账号创建失败");
    }
  }

  async function deleteChannel(item: ChannelSource) {
    if (!window.confirm(`确定删除“${item.name}”的二维码吗？删除后链接将立即失效。`)) return;
    try {
      await api.deleteChannel(item.id);
      channels.value = channels.value.filter((channel) => channel.id !== item.id);
      pushToast("success", "渠道二维码已删除");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "删除二维码失败");
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
      await loadAdminTab("questions");
      pushToast("success", "题库已新增");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "新增题库失败");
    } finally {
      questionBankSaving.value = false;
    }
  }

  async function createQuestion() {
    questionBankSaving.value = true;
    try {
      await api.createQuestion({
        ...questionForm,
        dimension: questionForm.dimension.trim() || null,
        text: questionForm.text.trim(),
        option_text: questionForm.option_text.trim() || null,
        is_active: true
      });
      questionBankDialog.value = null;
      await loadAdminTab("questions");
      pushToast("success", "题目已新增");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "新增题目失败");
    } finally {
      questionBankSaving.value = false;
    }
  }

  async function deleteQuestionModule(module: QuestionModule) {
    if (!window.confirm(`确定删除题库“${module.name}”吗？新客户将不再看到其中题目，历史报告不会受影响。`)) return;
    try {
      const result = await api.deleteQuestionModule(module.id);
      await loadAdminTab("questions");
      pushToast("success", result.message);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "删除题库失败");
    }
  }

  async function deleteQuestion(question: Question) {
    if (!window.confirm(`确定删除“${question.code}”吗？新客户将不再看到此题，历史报告不会受影响。`)) return;
    try {
      const result = await api.deleteQuestion(question.id);
      await loadAdminTab("questions");
      pushToast("success", result.message);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "删除题目失败");
    }
  }

  async function loadGatewayTab() {
    gatewayConfig.value = await api.gatewayConfig();
    hydrateGatewayForm();
  }

  function hydrateGatewayForm() {
    const config = gatewayConfig.value;
    if (!config) return;
    searchForm.search_provider = config.search_provider;
    searchForm.search_base_url = config.search_base_url || "";
    searchForm.search_timeout_seconds = config.search_timeout_seconds;
    searchForm.search_max_results = config.search_max_results;
    searchForm.search_model = config.search_model || "";
    llmForm.llm_base_url = config.llm_base_url || "";
    llmForm.llm_model = config.llm_model || "";
    // key 掩码不回填，留空提交即保留原值
    searchForm.search_api_key = "";
    llmForm.llm_api_key = "";
  }

  const searchTestResult = ref<{ ok: boolean; text: string } | null>(null);
  const llmTestResult = ref<{ ok: boolean; text: string } | null>(null);

  async function saveSearchConfig() {
    const formKey = searchForm.search_api_key.trim();
    const savedProvider = gatewayConfig.value?.search_provider;
    const providerChanged = Boolean(savedProvider && savedProvider !== searchForm.search_provider);

    // 与后端一致的本地预检，避免发出必然失败的请求
    if ((providerChanged || searchForm.search_provider === "custom") && searchForm.search_provider !== "deepseek" && !formKey) {
      pushToast("error", providerChanged ? "切换搜索服务商时必须填写新的搜索 API Key（不能沿用旧 Key）" : "自定义服务商必须填写新的搜索 API Key（不能沿用旧 Key）");
      return;
    }
    const baseUrl = searchForm.search_base_url.trim();
    if (searchForm.search_provider === "custom" && (!baseUrl || !baseUrl.startsWith("https://"))) {
      pushToast("error", "自定义服务商必须填写 https:// 开头的接口地址");
      return;
    }
    searchSaving.value = true;
    try {
      gatewayConfig.value = await api.saveSearchConfig({ ...searchForm });
      hydrateGatewayForm();
      pushToast("success", "搜索配置已保存");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "保存搜索配置失败");
    } finally {
      searchSaving.value = false;
    }
  }

  async function saveLlmConfig() {
    const llmBase = llmForm.llm_base_url.trim();
    const savedLlmBase = gatewayConfig.value?.llm_base_url || "";
    const llmBaseChanged = llmBase !== savedLlmBase;

    if (llmBase && !llmBase.startsWith("https://")) {
      pushToast("error", "LLM 接口地址必须以 https:// 开头");
      return;
    }
    if (llmBaseChanged && !llmForm.llm_api_key.trim()) {
      pushToast("error", "更换 LLM 接口地址时必须同时填写新的 LLM API Key（不能沿用旧 Key）");
      return;
    }

    llmSaving.value = true;
    try {
      gatewayConfig.value = await api.saveLlmConfig({ ...llmForm });
      hydrateGatewayForm();
      pushToast("success", "大模型配置已保存");
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "保存大模型配置失败");
    } finally {
      llmSaving.value = false;
    }
  }

  async function testSearchConfig() {
    const query = (leads.value[0]?.company_name || "测试公司").trim();
    const formKey = searchForm.search_api_key.trim();
    const savedProvider = gatewayConfig.value?.search_provider;
    const providerChanged = Boolean(savedProvider && savedProvider !== searchForm.search_provider);
    const baseUrl = searchForm.search_base_url.trim();

    // 点击前先本地预检，避免把必然失败的请求发到后端
    if (searchForm.search_provider === "custom") {
      if (!formKey) {
        searchTestResult.value = { ok: false, text: "自定义服务商必须填写新的搜索 API Key（不能沿用旧 Key）" };
        return;
      }
      if (!baseUrl || !baseUrl.startsWith("https://")) {
        searchTestResult.value = { ok: false, text: "自定义服务商需要填写 https:// 开头的接口地址" };
        return;
      }
    } else if (providerChanged && searchForm.search_provider !== "deepseek" && !formKey) {
      searchTestResult.value = { ok: false, text: "切换搜索服务商时必须填写新的搜索 API Key（不能沿用旧 Key）" };
      return;
    } else if (searchForm.search_provider !== "deepseek" && !formKey && !gatewayConfig.value?.search_api_key) {
      searchTestResult.value = { ok: false, text: "请先填写搜索 API Key（DeepSeek 可共用服务器 .env 中的 Key）" };
      return;
    }

    searchTesting.value = true;
    searchTestResult.value = null;
    try {
      const result = await api.testSearchConfig(query, {
        search_provider: searchForm.search_provider,
        search_api_key: formKey,
        search_base_url: searchForm.search_provider === "custom" ? baseUrl : null,
        search_timeout_seconds: searchForm.search_timeout_seconds,
        search_max_results: searchForm.search_max_results,
        search_model: searchForm.search_model.trim() || null,
      });
      if (result.ok) {
        searchTestResult.value = {
          ok: true,
          text: `连通成功：查询“${query}”返回 ${result.result_count} 条结果（${result.elapsed_ms}ms）${(result.first_results?.length ? `，如“${result.first_results[0]}”` : "")}`,
        };
      } else {
        searchTestResult.value = { ok: false, text: result.error || "搜索接口调用失败" };
      }
    } catch (err) {
      searchTestResult.value = { ok: false, text: err instanceof Error ? err.message : "测试失败" };
    } finally {
      searchTesting.value = false;
    }
  }

  async function testLlmConfig() {
    const llmBase = llmForm.llm_base_url.trim();
    const savedLlmBase = gatewayConfig.value?.llm_base_url || "";
    const baseChanged = llmBase !== savedLlmBase;

    if (llmBase && !llmBase.startsWith("https://")) {
      llmTestResult.value = { ok: false, text: "LLM 接口地址必须以 https:// 开头" };
      return;
    }
    if (llmBase && baseChanged && !llmForm.llm_api_key.trim()) {
      llmTestResult.value = { ok: false, text: "更换 LLM 接口地址时必须同时填写新的 LLM API Key（不能沿用旧 Key）" };
      return;
    }

    llmTesting.value = true;
    llmTestResult.value = null;
    try {
      const result = await api.testLlmConfig({
        llm_api_key: llmForm.llm_api_key.trim(),
        llm_base_url: llmBase || null,
        llm_model: llmForm.llm_model.trim() || null,
      });
      if (result.ok) {
        llmTestResult.value = { ok: true, text: `连通成功：${result.model} 回复“${result.reply}”（${result.elapsed_ms}ms）` };
      } else {
        llmTestResult.value = { ok: false, text: result.error || "大模型调用失败" };
      }
    } catch (err) {
      llmTestResult.value = { ok: false, text: err instanceof Error ? err.message : "测试失败" };
    } finally {
      llmTesting.value = false;
    }
  }

  const canExportLeads = computed(() => ["admin", "operator", "sales"].includes(adminUser.value?.role || ""));
  const canDeleteLeads = computed(() => adminUser.value?.role === "admin");
  const canManageQuestionBank = computed(() => ["admin", "operator"].includes(adminUser.value?.role || ""));
  const canManageGateway = computed(() => adminUser.value?.role === "admin");
  const leadIndustryOptions = computed(() => ["全部行业", ...Array.from(new Set(leadIndustrySource.value.map((lead) => lead.industry || "未填写").filter(Boolean)))]);

  function sourceLabel(code: string | null | undefined): string {
    if (!code) return "未标记来源";
    return channels.value.find((channel) => channel.code === code)?.name || code;
  }

  // 筛选与排序均由服务端完成，前端只负责分页切片
  const filteredLeads = computed(() => leads.value);
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

  // 任一筛选条件变化 → 重新从服务端拉取并回到第一页
  watch(
    [leadSortOrder, leadIndustryFilter, leadLevelFilter, leadCreatedFrom, leadCreatedTo, leadViewFilter, leadProcessingFilter, leadExportFilter],
    () => {
      void loadLeads();
    }
  );

  watch(leadPageSize, resetLeadPage);

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
    leadCreatedFrom,
    leadCreatedTo,
    leadLevelFilter,
    leadViewFilter,
    leadProcessingFilter,
    leadExportFilter,
    leadPageSize,
    leadPage,
    leadRuleDialogOpen,
    leadDetailOpen,
    leadDetailLoading,
    selectedLeadDetail,
    researchRunning,
    resumeDeliveryRunning,
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
    leadDetailReportHtml,
    selectedLeadScoreRate,
    loginAdmin,
    loadAdminShell,
    loadAdminTab,
    resetLeadPage,
    goLeadPage,
    openLeadDetail,
    openLeadDetailById,
    closeLeadDetail,
    runLeadResearch,
    resumeReportDelivery,
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
  };
}

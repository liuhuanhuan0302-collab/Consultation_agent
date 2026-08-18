/** 客户自测流程 — 会话、企业信息、答题进度、草稿、提交与报告轮询。 */

import { computed, nextTick, reactive, ref, watch, type Ref } from "vue";

import { api } from "../api";
import type { QuestionModule, Report, ScoreResponse } from "../types";
import { appUrl, sourceFromUrl } from "../utils/appPaths";
import { isValidEmail } from "../utils/format";
import { error } from "./feedback";

export type Step = "intro" | "info" | "questionnaire" | "submitted" | "report";
export type LeadFormState = {
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

export function useQuestionnaire() {
  const step = ref<Step>("intro");
  const sessionToken = ref<string | null>(localStorage.getItem("diagnosis_session"));
  const leadId = ref<number | null>(Number(localStorage.getItem("diagnosis_lead_id")) || null);
  const submissionId = ref<number | null>(Number(localStorage.getItem("submission_id")) || null);
  const modules = ref<QuestionModule[]>([]);
  const moduleIndex = ref(Number(localStorage.getItem("diagnosis_module_index")) || 0);
  const answers = ref<Record<number, number>>(JSON.parse(localStorage.getItem("diagnosis_answers") || "{}"));
  const score = ref<ScoreResponse | null>(null);
  const report = ref<Report | null>(null);
  const busy = ref(false);
  const draftSaved = ref(false);
  const reportWaitSeconds = ref(0);
  const deliveryStatus = ref<string | null>(null);
  const queuePosition = ref<number | null>(null);
  const reportPollTimer = ref<number | null>(null);
  const reportWaitTimer = ref<number | null>(null);
  const missingNoticeVisible = ref(false);
  const missingNoticeMessage = ref("");
  const missingNoticeTimer = ref<number | null>(null);

  const leadForm = reactive<LeadFormState>(loadSavedLeadForm());

  const phoneWechatSame = ref(false);
  const selectedAiFocus = ref<string[]>([]);
  const aiFocusOther = ref("");

  const questions = computed(() => modules.value.flatMap((module) => module.questions));
  const answeredCount = computed(() => Object.keys(answers.value).length);
  const currentModule = computed(() => modules.value[moduleIndex.value]);
  const progress = computed(() => (questions.value.length ? answeredCount.value / questions.value.length : 0));

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

  function answersToList() {
    return Object.entries(answers.value).map(([question_id, itemScore]) => ({ question_id: Number(question_id), score: Number(itemScore) }));
  }

  function persistLeadForm() {
    localStorage.setItem("diagnosis_lead_form", JSON.stringify({ ...leadForm }));
  }

  function persistStep() {
    localStorage.setItem("diagnosis_step", step.value);
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
    window.location.assign(appUrl(`/report/${token}`));
  }

  async function checkSubmittedReport(): Promise<boolean> {
    if (!sessionToken.value) return false;
    const cachedReportToken = localStorage.getItem("diagnosis_report_token");
    if (!submissionId.value && !cachedReportToken) return false;
    try {
      const currentReport = submissionId.value
        ? await api.submissionReport(submissionId.value, sessionToken.value)
        : await api.publicReport(cachedReportToken!);
      report.value = currentReport;
      deliveryStatus.value = currentReport.delivery_status ?? null;
      queuePosition.value = currentReport.queue_position ?? null;
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
    deliveryStatus.value = null;
    queuePosition.value = null;
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
    if (submissionId.value && sessionToken.value) {
      await api.saveDraft(submissionId.value, answersToList(), sessionToken.value).catch(() => undefined);
    }
    draftSaved.value = true;
    setTimeout(() => { draftSaved.value = false; }, 2000);
  }

  async function submitQuestionnaire() {
    if (!submissionId.value || !sessionToken.value) return;
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
      const result = await api.submitQuestionnaire(submissionId.value, answersToList(), sessionToken.value);
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

  return {
    step,
    sessionToken,
    leadId,
    submissionId,
    modules,
    moduleIndex,
    answers,
    score,
    report,
    busy,
    draftSaved,
    reportWaitSeconds,
    deliveryStatus,
    queuePosition,
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
  };
}

export type QuestionnaireState = ReturnType<typeof useQuestionnaire>;
export type ScoreRef = Ref<ScoreResponse | null>;

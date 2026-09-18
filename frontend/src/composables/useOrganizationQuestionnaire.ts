import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { ApiError, api } from "../api";
import type {
  OrganizationAnswer,
  OrganizationCompanySuggestion,
  OrganizationSubmissionCreate,
  QuestionModule,
} from "../types";
import { appUrl } from "../utils/appPaths";

export type OrganizationStep = "info" | "questionnaire" | "success";

export type OrganizationInfo = OrganizationSubmissionCreate;

const STORAGE_KEYS = {
  id: "organization_submission_id",
  accessToken: "organization_access_token",
  info: "organization_info",
  answers: "organization_answers",
  moduleIndex: "organization_module_index",
  step: "organization_step",
} as const;

const defaultInfo: OrganizationInfo = {
  company_name_input: "",
  company_name: "",
  respondent_name: "",
  department: "",
  position: "",
};

function readStoredInfo(): OrganizationInfo {
  const raw = sessionStorage.getItem(STORAGE_KEYS.info);
  if (!raw) return { ...defaultInfo };
  try {
    return { ...defaultInfo, ...JSON.parse(raw) };
  } catch {
    return { ...defaultInfo };
  }
}

function readStoredAnswers(): Record<number, number> {
  const raw = sessionStorage.getItem(STORAGE_KEYS.answers);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const restored: Record<number, number> = {};
    for (const [key, value] of Object.entries(parsed)) {
      const questionId = Number(key);
      const answerValue = Number(value);
      if (Number.isInteger(questionId) && Number.isInteger(answerValue) && answerValue >= 0 && answerValue <= 4) {
        restored[questionId] = answerValue;
      }
    }
    return restored;
  } catch {
    return {};
  }
}

function readStoredModuleIndex(): number {
  const value = Number(sessionStorage.getItem(STORAGE_KEYS.moduleIndex));
  return Number.isInteger(value) && value >= 0 ? value : 0;
}

function apiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  if (error.status === 400 || error.status === 422) return error.message || "请检查填写内容或答案";
  if (error.status === 401 || error.status === 403) return "答卷凭证已失效，请重新开始组织诊断";
  if (error.status === 409) return "这份组织诊断已经提交，请勿重复提交";
  if (error.status === 429) return "请求过于频繁，请稍后再试";
  if (error.status >= 500) return "服务暂时异常，请稍后再试";
  return error.message || fallback;
}

export function useOrganizationQuestionnaire() {
  const step = ref<OrganizationStep>((sessionStorage.getItem(STORAGE_KEYS.step) as OrganizationStep) || "info");
  const info = reactive<OrganizationInfo>(readStoredInfo());
  const submissionId = ref<number | null>(Number(sessionStorage.getItem(STORAGE_KEYS.id)) || null);
  const accessToken = ref<string | null>(sessionStorage.getItem(STORAGE_KEYS.accessToken));
  const modules = ref<QuestionModule[]>([]);
  const moduleIndex = ref(readStoredModuleIndex());
  const answers = ref<Record<number, number>>(readStoredAnswers());
  const selectedCompanyName = ref(
    info.company_name && info.company_name === info.company_name_input ? info.company_name : "",
  );

  const suggestions = ref<OrganizationCompanySuggestion[]>([]);
  const suggestionsLoading = ref(false);
  const suggestionsOpen = ref(false);
  const autocompleteMessage = ref("");
  const busy = ref(false);
  const draftSaving = ref(false);
  const draftSaved = ref(false);
  const error = ref("");
  const missingNotice = ref("");

  let suggestionTimer: number | null = null;
  let suggestionBlurTimer: number | null = null;
  let suggestionController: AbortController | null = null;
  let draftSavedTimer: number | null = null;

  const questions = computed(() => modules.value.flatMap((module) => module.questions));
  const currentModule = computed(() => modules.value[moduleIndex.value]);
  const answeredCount = computed(() => Object.keys(answers.value).length);
  const progress = computed(() => (questions.value.length ? answeredCount.value / questions.value.length : 0));
  const allAnswered = computed(() => questions.value.length > 0 && answeredCount.value === questions.value.length);

  function persistState() {
    sessionStorage.setItem(STORAGE_KEYS.info, JSON.stringify({ ...info }));
    sessionStorage.setItem(STORAGE_KEYS.step, step.value);
    sessionStorage.setItem(STORAGE_KEYS.moduleIndex, String(moduleIndex.value));
    sessionStorage.setItem(STORAGE_KEYS.answers, JSON.stringify(answers.value));
  }

  function persistSubmission(id: number, token: string) {
    submissionId.value = id;
    accessToken.value = token;
    sessionStorage.setItem(STORAGE_KEYS.id, String(id));
    sessionStorage.setItem(STORAGE_KEYS.accessToken, token);
  }

  function parseOptionLabels(optionText: string | null | undefined): { value: number; label: string }[] {
    if (!optionText) return [];
    return optionText
      .split("；")
      .map((item) => {
        const [value, ...labelParts] = item.trim().split("=");
        return { value: Number.parseInt(value, 10), label: labelParts.join("=").trim() || value };
      })
      .filter((item) => Number.isInteger(item.value) && item.value >= 0 && item.value <= 4);
  }

  function getGlobalIndex(module: QuestionModule, questionIndex: number): number {
    let index = 0;
    for (const item of modules.value) {
      if (item.id === module.id) break;
      index += item.questions.length;
    }
    return index + questionIndex + 1;
  }

  function moduleDone(module: QuestionModule): boolean {
    return module.questions.every((question) => answers.value[question.id] !== undefined);
  }

  function isAnswerSelected(questionId: number, value: number): boolean {
    return answers.value[questionId] === value;
  }

  function answersToPayload(): OrganizationAnswer[] {
    return Object.entries(answers.value).map(([questionId, answerValue]) => ({
      question_id: Number(questionId),
      answer_value: Number(answerValue),
    }));
  }

  function focusQuestion(questionId: number) {
    window.setTimeout(() => {
      document.getElementById(`organization-question-${questionId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
  }

  function showMissingQuestion(module: QuestionModule, index: number): boolean {
    const missing = module.questions.find((question) => answers.value[question.id] === undefined);
    if (!missing) return false;
    moduleIndex.value = index;
    missingNotice.value = `当前页面还有题目未答，请先完成后再继续：${missing.code}`;
    focusQuestion(missing.id);
    persistState();
    return true;
  }

  function clearSuggestionRequest() {
    if (suggestionTimer !== null) {
      window.clearTimeout(suggestionTimer);
      suggestionTimer = null;
    }
    if (suggestionController) {
      suggestionController.abort();
      suggestionController = null;
    }
    suggestionsLoading.value = false;
  }

  async function fetchSuggestions(query: string) {
    const controller = new AbortController();
    suggestionController = controller;
    suggestionsLoading.value = true;
    try {
      const response = await api.organizationCompanySuggestions(query, controller.signal);
      if (info.company_name_input.trim() !== query) return;
      suggestions.value = response.items.slice(0, 10);
      suggestionsOpen.value = true;
      autocompleteMessage.value = suggestions.value.length ? "" : "未找到已有企业，可继续使用当前名称";
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      if (requestError instanceof ApiError && requestError.status === 429) {
        suggestions.value = [];
        suggestionsOpen.value = true;
        autocompleteMessage.value = "企业匹配暂时繁忙，您仍可直接填写完整企业名称继续。";
        return;
      }
      suggestions.value = [];
      suggestionsOpen.value = true;
      autocompleteMessage.value = "企业匹配暂时不可用，您仍可直接填写完整企业名称继续。";
    } finally {
      if (suggestionController === controller) {
        suggestionController = null;
        suggestionsLoading.value = false;
      }
    }
  }

  function handleCompanyInput() {
    if (info.company_name_input.trim() !== selectedCompanyName.value) {
      selectedCompanyName.value = "";
      info.company_name = info.company_name_input;
    }
    clearSuggestionRequest();
    suggestions.value = [];
    suggestionsOpen.value = false;
    autocompleteMessage.value = "";
    persistState();
    const query = info.company_name_input.trim();
    if (query.length < 2) return;
    suggestionsOpen.value = true;
    suggestionsLoading.value = true;
    suggestionTimer = window.setTimeout(() => {
      suggestionTimer = null;
      void fetchSuggestions(query);
    }, 300);
  }

  function handleCompanyFocus() {
    if (suggestions.value.length || autocompleteMessage.value) suggestionsOpen.value = true;
  }

  function handleCompanyBlur() {
    if (suggestionBlurTimer !== null) window.clearTimeout(suggestionBlurTimer);
    suggestionBlurTimer = window.setTimeout(() => {
      suggestionsOpen.value = false;
      suggestionBlurTimer = null;
    }, 150);
  }

  function selectCompany(company: string) {
    if (suggestionBlurTimer !== null) {
      window.clearTimeout(suggestionBlurTimer);
      suggestionBlurTimer = null;
    }
    clearSuggestionRequest();
    selectedCompanyName.value = company;
    info.company_name_input = company;
    info.company_name = company;
    suggestions.value = [];
    suggestionsOpen.value = false;
    autocompleteMessage.value = "";
    persistState();
  }

  function validateInfo(): boolean {
    const fields: [keyof OrganizationInfo, string][] = [
      ["company_name_input", "企业名称"],
      ["respondent_name", "姓名"],
      ["department", "部门"],
      ["position", "职位"],
    ];
    for (const [field, label] of fields) {
      if (!info[field].trim()) {
        error.value = `请填写${label}`;
        return false;
      }
    }
    return true;
  }

  async function loadQuestions() {
    modules.value = await api.questions();
    if (moduleIndex.value >= modules.value.length) moduleIndex.value = 0;
    const activeIds = new Set(questions.value.map((question) => question.id));
    answers.value = Object.fromEntries(
      Object.entries(answers.value).filter(([questionId, answerValue]) => activeIds.has(Number(questionId)) && Number.isInteger(answerValue) && answerValue >= 0 && answerValue <= 4),
    );
    persistState();
  }

  async function startOrganization() {
    error.value = "";
    if (!validateInfo()) return;
    busy.value = true;
    try {
      const payload: OrganizationSubmissionCreate = {
        company_name_input: info.company_name_input.trim(),
        company_name: (selectedCompanyName.value || info.company_name_input).trim(),
        respondent_name: info.respondent_name.trim(),
        department: info.department.trim(),
        position: info.position.trim(),
      };
      const created = await api.createOrganizationSubmission(payload);
      Object.assign(info, payload);
      persistSubmission(created.id, created.access_token);
      answers.value = {};
      moduleIndex.value = 0;
      await loadQuestions();
      step.value = "questionnaire";
      persistState();
    } catch (requestError) {
      error.value = apiErrorMessage(requestError, "组织诊断启动失败，请稍后再试");
    } finally {
      busy.value = false;
    }
  }

  function selectAnswer(questionId: number, value: number) {
    if (!Number.isInteger(value) || value < 0 || value > 4) return;
    answers.value = { ...answers.value, [questionId]: value };
    missingNotice.value = "";
    persistState();
  }

  async function saveDraft(): Promise<boolean> {
    if (!submissionId.value || !accessToken.value || !answers.value || !Object.keys(answers.value).length) return true;
    draftSaving.value = true;
    try {
      await api.saveOrganizationAnswers(submissionId.value, answersToPayload(), accessToken.value);
      draftSaved.value = true;
      if (draftSavedTimer !== null) window.clearTimeout(draftSavedTimer);
      draftSavedTimer = window.setTimeout(() => {
        draftSaved.value = false;
        draftSavedTimer = null;
      }, 2200);
      return true;
    } catch (requestError) {
      error.value = apiErrorMessage(requestError, "草稿保存失败，请稍后再试");
      return false;
    } finally {
      draftSaving.value = false;
    }
  }

  async function goToModule(index: number) {
    if (index < 0 || index >= modules.value.length || index === moduleIndex.value) return;
    if (index > moduleIndex.value) {
      const blockedIndex = modules.value.findIndex((module, moduleIdx) => moduleIdx < index && !moduleDone(module));
      if (blockedIndex >= 0) {
        showMissingQuestion(modules.value[blockedIndex], blockedIndex);
        return;
      }
      if (!(await saveDraft())) return;
    }
    moduleIndex.value = index;
    missingNotice.value = "";
    persistState();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function goNextModule() {
    const module = currentModule.value;
    if (!module) return;
    if (showMissingQuestion(module, moduleIndex.value)) return;
    if (moduleIndex.value < modules.value.length - 1) await goToModule(moduleIndex.value + 1);
  }

  function goPrevModule() {
    if (moduleIndex.value > 0) void goToModule(moduleIndex.value - 1);
  }

  async function submitOrganization() {
    if (!submissionId.value || !accessToken.value || !allAnswered.value) {
      const missing = questions.value.find((question) => answers.value[question.id] === undefined);
      if (missing) {
        const targetIndex = modules.value.findIndex((module) => module.questions.some((question) => question.id === missing.id));
        if (targetIndex >= 0) moduleIndex.value = targetIndex;
        missingNotice.value = `还有题目未填写：${missing.code}`;
        focusQuestion(missing.id);
      }
      return;
    }
    busy.value = true;
    error.value = "";
    try {
      await api.submitOrganizationAnswers(submissionId.value, answersToPayload(), accessToken.value);
      step.value = "success";
      persistState();
    } catch (requestError) {
      error.value = apiErrorMessage(requestError, "提交失败，请稍后再试");
    } finally {
      busy.value = false;
    }
  }

  function finish() {
    Object.values(STORAGE_KEYS).forEach((key) => sessionStorage.removeItem(key));
    window.location.assign(appUrl("/"));
  }

  async function restoreOrganization() {
    if (step.value !== "questionnaire" || !submissionId.value || !accessToken.value) return;
    busy.value = true;
    try {
      await loadQuestions();
    } catch (requestError) {
      error.value = apiErrorMessage(requestError, "问卷加载失败，请稍后刷新重试");
    } finally {
      busy.value = false;
    }
  }

  function handleBeforeUnload() {
    if (step.value !== "success") persistState();
  }

  onMounted(() => {
    window.addEventListener("beforeunload", handleBeforeUnload);
    void restoreOrganization();
  });

  onBeforeUnmount(() => {
    window.removeEventListener("beforeunload", handleBeforeUnload);
    clearSuggestionRequest();
    if (suggestionBlurTimer !== null) window.clearTimeout(suggestionBlurTimer);
    if (draftSavedTimer !== null) window.clearTimeout(draftSavedTimer);
  });

  return {
    step,
    info,
    submissionId,
    modules,
    moduleIndex,
    answers,
    suggestions,
    suggestionsLoading,
    suggestionsOpen,
    autocompleteMessage,
    busy,
    draftSaving,
    draftSaved,
    error,
    missingNotice,
    questions,
    currentModule,
    answeredCount,
    progress,
    allAnswered,
    parseOptionLabels,
    getGlobalIndex,
    moduleDone,
    isAnswerSelected,
    handleCompanyInput,
    handleCompanyFocus,
    handleCompanyBlur,
    selectCompany,
    startOrganization,
    selectAnswer,
    saveDraft,
    goToModule,
    goNextModule,
    goPrevModule,
    submitOrganization,
    finish,
  };
}

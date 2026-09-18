import { computed, ref } from "vue";

import { ApiError, api, type OrganizationAdminCompanyParams, type OrganizationAdminSubmissionParams } from "../api";
import type { OrganizationCompanyDetailResponse, OrganizationCompanyListResponse, OrganizationSubmissionAdminDetail } from "../types";

export function useOrganizationAdmin() {
  const companies = ref<OrganizationCompanyListResponse | null>(null);
  const companyLoading = ref(false);
  const companyError = ref("");
  const companyPage = ref(1);
  const companyPageSize = 10;

  const selectedCompany = ref("");
  const companyDetail = ref<OrganizationCompanyDetailResponse | null>(null);
  const submissionLoading = ref(false);
  const submissionError = ref("");
  const submissionPage = ref(1);
  const submissionPageSize = 10;
  const selectedSubmission = ref<OrganizationSubmissionAdminDetail | null>(null);
  const submissionDetailLoading = ref(false);
  const submissionDetailError = ref("");
  const exporting = ref(false);
  const reportGenerating = ref(false);
  const reportDownloading = ref<number | null>(null);

  type PaginationItem = number | "ellipsis-left" | "ellipsis-right";

  function paginationItems(currentPage: number, totalPages: number): PaginationItem[] {
    if (totalPages <= 0) return [];
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
    const current = Math.min(totalPages, Math.max(1, currentPage));
    if (current <= 4) return [1, 2, 3, 4, 5, "ellipsis-right", totalPages];
    if (current >= totalPages - 3) {
      return [1, "ellipsis-left", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
    }
    return [1, "ellipsis-left", current - 1, current, current + 1, "ellipsis-right", totalPages];
  }

  const companyPageStart = computed(() => companies.value?.total ? (companyPage.value - 1) * companyPageSize + 1 : 0);
  const companyPageEnd = computed(() => Math.min(companyPage.value * companyPageSize, companies.value?.total || 0));
  const companyPaginationPages = computed(() => paginationItems(companyPage.value, companies.value?.pages || 0));
  const submissionPageStart = computed(() => companyDetail.value?.total ? (submissionPage.value - 1) * submissionPageSize + 1 : 0);
  const submissionPageEnd = computed(() => Math.min(submissionPage.value * submissionPageSize, companyDetail.value?.total || 0));
  const submissionPaginationPages = computed(() => paginationItems(submissionPage.value, companyDetail.value?.pages || 0));

  function errorMessage(error: unknown, fallback: string) {
    if (error instanceof ApiError && error.status === 401) return "登录状态已失效，请重新登录。";
    return error instanceof Error ? error.message : fallback;
  }

  function companyQuery(page: number): OrganizationAdminCompanyParams {
    return {
      has_submitted: true,
      page,
      page_size: companyPageSize,
    };
  }

  async function loadCompanies(page = 1) {
    companyLoading.value = true;
    companyError.value = "";
    try {
      companies.value = await api.organizationAdminCompanies(companyQuery(page));
      companyPage.value = page;
    } catch (error) {
      companyError.value = errorMessage(error, "组织诊断企业列表加载失败");
    } finally {
      companyLoading.value = false;
    }
  }

  async function goCompanyPage(targetPage: number) {
    const maximumPage = Math.max(1, companies.value?.pages || 1);
    await loadCompanies(Math.min(maximumPage, Math.max(1, targetPage)));
  }

  function submissionQuery(page: number): OrganizationAdminSubmissionParams {
    return {
      status: "submitted",
      page,
      page_size: submissionPageSize,
    };
  }

  async function loadSubmissions(page = 1) {
    if (!selectedCompany.value) return;
    submissionLoading.value = true;
    submissionError.value = "";
    try {
      companyDetail.value = await api.organizationAdminCompanySubmissions(selectedCompany.value, submissionQuery(page));
      submissionPage.value = page;
    } catch (error) {
      submissionError.value = errorMessage(error, "组织诊断答卷加载失败");
    } finally {
      submissionLoading.value = false;
    }
  }

  async function goSubmissionPage(targetPage: number) {
    const maximumPage = Math.max(1, companyDetail.value?.pages || 1);
    await loadSubmissions(Math.min(maximumPage, Math.max(1, targetPage)));
  }

  async function openCompany(companyName: string) {
    selectedCompany.value = companyName;
    selectedSubmission.value = null;
    submissionDetailError.value = "";
    companyDetail.value = null;
    submissionPage.value = 1;
    await loadSubmissions(1);
  }

  function closeCompany() {
    selectedCompany.value = "";
    companyDetail.value = null;
    selectedSubmission.value = null;
    submissionError.value = "";
  }

  async function openSubmission(submissionId: number) {
    submissionDetailLoading.value = true;
    submissionDetailError.value = "";
    try {
      selectedSubmission.value = await api.organizationAdminSubmissionDetail(submissionId);
    } catch (error) {
      submissionDetailError.value = errorMessage(error, "组织诊断答卷详情加载失败");
    } finally {
      submissionDetailLoading.value = false;
    }
  }

  async function queueReportGeneration() {
    if (!selectedSubmission.value || reportGenerating.value) return;
    reportGenerating.value = true;
    submissionDetailError.value = "";
    try {
      await api.organizationAdminGenerateReport(selectedSubmission.value.id);
      await openSubmission(selectedSubmission.value.id);
    } catch (error) {
      submissionDetailError.value = errorMessage(error, "组织分析任务创建失败");
    } finally {
      reportGenerating.value = false;
    }
  }

  async function downloadOrganizationReport(reportId: number) {
    if (reportDownloading.value !== null) return;
    reportDownloading.value = reportId;
    submissionDetailError.value = "";
    try {
      await api.organizationAdminReportPdf(reportId);
    } catch (error) {
      submissionDetailError.value = errorMessage(error, "组织分析PDF下载失败");
    } finally {
      reportDownloading.value = null;
    }
  }

  function closeSubmission() {
    selectedSubmission.value = null;
    submissionDetailError.value = "";
  }

  async function exportSubmissions() {
    if (!selectedCompany.value) return;
    exporting.value = true;
    submissionError.value = "";
    try {
      await api.organizationAdminExport({
        company_name: selectedCompany.value,
        status: "submitted",
      });
    } catch (error) {
      submissionError.value = errorMessage(error, "组织诊断导出失败");
    } finally {
      exporting.value = false;
    }
  }

  return {
    companies,
    companyLoading,
    companyError,
    companyPage,
    companyPageSize,
    companyPageStart,
    companyPageEnd,
    companyPaginationPages,
    selectedCompany,
    companyDetail,
    submissionLoading,
    submissionError,
    submissionPage,
    submissionPageSize,
    submissionPageStart,
    submissionPageEnd,
    submissionPaginationPages,
    selectedSubmission,
    submissionDetailLoading,
    submissionDetailError,
    exporting,
    reportGenerating,
    reportDownloading,
    loadCompanies,
    goCompanyPage,
    openCompany,
    closeCompany,
    loadSubmissions,
    goSubmissionPage,
    openSubmission,
    queueReportGeneration,
    downloadOrganizationReport,
    closeSubmission,
    exportSubmissions,
  };
}

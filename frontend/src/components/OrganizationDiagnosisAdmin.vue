<script setup lang="ts">
import { onMounted } from "vue";
import { ArrowDownToLine, ArrowLeft, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Eye, RefreshCw } from "lucide-vue-next";

import OrganizationSubmissionDetail from "./OrganizationSubmissionDetail.vue";
import { useOrganizationAdmin } from "../composables/useOrganizationAdmin";
import { formatDateTime } from "../utils/format";

const {
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
} = useOrganizationAdmin();

onMounted(() => {
  void loadCompanies();
});

function statusLabel(status: string) {
  return status === "submitted" ? "已提交" : "草稿";
}
</script>

<template>
  <div class="organization-admin-page" :class="{ 'organization-company-selected': selectedCompany }">
    <template v-if="!selectedCompany">
      <section class="table-section">
        <header class="organization-list-header table-actions">
          <div>
            <p class="eyebrow">组织诊断</p>
            <h2>企业列表</h2>
          </div>
          <button class="secondary" type="button" :disabled="companyLoading" @click="loadCompanies(companyPage)"><RefreshCw :size="17" /> {{ companyLoading ? "刷新中..." : "刷新" }}</button>
        </header>
        <p v-if="companyError" class="organization-error" role="alert">{{ companyError }}</p>
        <div v-if="companyLoading && !companies" class="loading">组织诊断企业加载中...</div>
        <div v-else-if="companies" class="leads-table-wrap organization-table-wrap organization-company-list-wrap">
          <table class="leads-table organization-data-table organization-company-table">
            <thead><tr><th>企业名称</th><th>已提交</th><th>草稿</th><th>部门数</th><th>最近提交</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="item in companies.items" :key="item.company_name">
                <td><strong>{{ item.company_name }}</strong></td>
                <td>{{ item.submitted_count }}</td>
                <td>{{ item.draft_count }}</td>
                <td>{{ item.department_count }}</td>
                <td>{{ item.latest_submitted_at ? formatDateTime(item.latest_submitted_at) : "-" }}</td>
                <td><button class="text-action" type="button" @click="openCompany(item.company_name)"><Eye :size="15" /> 查看</button></td>
              </tr>
              <tr v-if="!companies.items.length"><td colspan="6" class="empty-cell">没有符合条件的组织诊断企业</td></tr>
            </tbody>
          </table>
        </div>
        <footer v-if="companies" class="pagination organization-list-pagination">
          <span>显示 {{ companyPageStart }}-{{ companyPageEnd }} / {{ companies.total }}</span>
          <nav class="pagination-nav" aria-label="组织诊断企业分页">
            <button class="secondary pagination-edge" type="button" :disabled="companyPage <= 1 || companyLoading" aria-label="第一页" title="第一页" @click="goCompanyPage(1)"><ChevronsLeft :size="16" /><span class="pagination-label">首页</span></button>
            <button class="secondary pagination-edge" type="button" :disabled="companyPage <= 1 || companyLoading" aria-label="上一页" @click="goCompanyPage(companyPage - 1)"><ChevronLeft :size="16" /><span class="pagination-label">上一页</span></button>
            <div class="pagination-pages">
              <template v-for="item in companyPaginationPages" :key="item">
                <button v-if="typeof item === 'number'" class="pagination-page" :class="{ active: item === companyPage }" type="button" :aria-current="item === companyPage ? 'page' : undefined" :aria-label="`第 ${item} 页`" :disabled="companyLoading" @click="goCompanyPage(item)">{{ item }}</button>
                <span v-else class="pagination-ellipsis" aria-hidden="true">…</span>
              </template>
            </div>
            <button class="secondary pagination-edge" type="button" :disabled="companyPage >= companies.pages || companyLoading" aria-label="下一页" @click="goCompanyPage(companyPage + 1)"><span class="pagination-label">下一页</span><ChevronRight :size="16" /></button>
            <button class="secondary pagination-edge" type="button" :disabled="companyPage >= companies.pages || companyLoading" aria-label="最后一页" title="最后一页" @click="goCompanyPage(companies.pages)"><span class="pagination-label">尾页</span><ChevronsRight :size="16" /></button>
          </nav>
        </footer>
      </section>
    </template>

    <template v-else-if="!selectedSubmission">
      <section class="table-section lead-detail-page organization-company-detail" aria-labelledby="organization-company-detail-title">
        <header class="organization-admin-header lead-detail-page-header">
          <div class="organization-detail-title">
            <p class="eyebrow">企业详情</p>
            <h2 id="organization-company-detail-title">{{ selectedCompany }}</h2>
          </div>
          <div class="organization-header-actions lead-detail-actions">
            <button class="secondary" type="button" :disabled="exporting || submissionLoading" @click="exportSubmissions"><ArrowDownToLine :size="17" /> {{ exporting ? "导出中..." : "导出已提交答卷" }}</button>
            <button class="secondary organization-back" type="button" @click="closeCompany"><ArrowLeft :size="16" /> 返回企业列表</button>
          </div>
        </header>
        <p v-if="submissionError" class="organization-error" role="alert">{{ submissionError }}</p>
        <div v-if="submissionLoading && !companyDetail" class="loading">组织诊断答卷加载中...</div>
        <div v-else-if="companyDetail" class="leads-table-wrap organization-table-wrap organization-submission-list-wrap">
          <table class="leads-table organization-data-table organization-submission-table">
            <thead><tr><th>姓名</th><th>部门</th><th>职位</th><th>状态</th><th>提交时间</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="item in companyDetail.items" :key="item.id">
                <td>{{ item.respondent_name }}</td><td>{{ item.department }}</td><td>{{ item.position }}</td><td><span :class="['organization-status', item.status]">{{ statusLabel(item.status) }}</span></td><td>{{ item.submitted_at ? formatDateTime(item.submitted_at) : "-" }}</td>
                <td><button class="text-action" type="button" @click="openSubmission(item.id)"><Eye :size="15" /> 查看答卷</button></td>
              </tr>
              <tr v-if="!companyDetail.items.length"><td colspan="6" class="empty-cell">没有符合条件的组织诊断答卷</td></tr>
            </tbody>
          </table>
        </div>
        <footer v-if="companyDetail" class="pagination organization-list-pagination">
          <span>显示 {{ submissionPageStart }}-{{ submissionPageEnd }} / {{ companyDetail.total }}</span>
          <nav class="pagination-nav" aria-label="组织诊断答卷分页">
            <button class="secondary pagination-edge" type="button" :disabled="submissionPage <= 1 || submissionLoading" aria-label="第一页" title="第一页" @click="goSubmissionPage(1)"><ChevronsLeft :size="16" /><span class="pagination-label">首页</span></button>
            <button class="secondary pagination-edge" type="button" :disabled="submissionPage <= 1 || submissionLoading" aria-label="上一页" @click="goSubmissionPage(submissionPage - 1)"><ChevronLeft :size="16" /><span class="pagination-label">上一页</span></button>
            <div class="pagination-pages">
              <template v-for="item in submissionPaginationPages" :key="item">
                <button v-if="typeof item === 'number'" class="pagination-page" :class="{ active: item === submissionPage }" type="button" :aria-current="item === submissionPage ? 'page' : undefined" :aria-label="`第 ${item} 页`" :disabled="submissionLoading" @click="goSubmissionPage(item)">{{ item }}</button>
                <span v-else class="pagination-ellipsis" aria-hidden="true">…</span>
              </template>
            </div>
            <button class="secondary pagination-edge" type="button" :disabled="submissionPage >= companyDetail.pages || submissionLoading" aria-label="下一页" @click="goSubmissionPage(submissionPage + 1)"><span class="pagination-label">下一页</span><ChevronRight :size="16" /></button>
            <button class="secondary pagination-edge" type="button" :disabled="submissionPage >= companyDetail.pages || submissionLoading" aria-label="最后一页" title="最后一页" @click="goSubmissionPage(companyDetail.pages)"><span class="pagination-label">尾页</span><ChevronsRight :size="16" /></button>
          </nav>
        </footer>
      </section>

      <section v-if="submissionDetailLoading" class="table-section loading">答卷详情加载中...</section>
      <p v-if="submissionDetailError" class="organization-error" role="alert">{{ submissionDetailError }}</p>
    </template>

    <template v-else>
      <p v-if="submissionDetailError" class="organization-error" role="alert">{{ submissionDetailError }}</p>
      <OrganizationSubmissionDetail
        :detail="selectedSubmission"
        :report-generating="reportGenerating"
        :report-downloading="reportDownloading"
        @close="closeSubmission"
        @generate-report="queueReportGeneration"
        @download-report="downloadOrganizationReport"
      />
    </template>
  </div>
</template>

<style scoped>
.organization-admin-page { align-content: start; display: flex; flex-direction: column; gap: 18px; height: 100%; margin: 0 auto; min-width: 0; overflow-x: hidden; width: 100%; }
.organization-admin-page > .table-section { border-radius: 8px; box-sizing: border-box; display: flex; flex: 1 1 auto; flex-direction: column; min-height: 0; min-width: 0; overflow: hidden; padding: 16px; width: 100%; }
.organization-admin-page > .table-section.loading { flex: 0 0 auto; }
.organization-admin-header { align-items: center; display: flex; gap: 18px; justify-content: space-between; }
.organization-admin-header h2 { color: #0f172a; font-size: 28px; line-height: 1.18; margin: 0; }
.organization-admin-header > button { align-items: center; display: inline-flex; flex: 0 0 auto; gap: 7px; min-height: 42px; }
.organization-list-header { margin-bottom: 14px; }
.organization-list-header h2 { margin: 0; }
.organization-list-header > button { align-items: center; display: inline-flex; gap: 7px; min-height: 42px; }
.organization-header-actions { display: flex; gap: 8px; }
.organization-table-wrap { border: 1px solid #e5eaf0; border-radius: 8px; flex: 1 1 auto; min-height: 0; min-width: 0; overflow: auto; width: 100%; }
.organization-table-wrap table { table-layout: auto; }
.organization-table-wrap th, .organization-table-wrap td { line-height: 1.2; overflow: hidden; padding: 0 10px; text-overflow: ellipsis; vertical-align: middle; white-space: nowrap; }
.organization-table-wrap th { background: #fff; height: 38px; position: sticky; top: 0; z-index: 1; }
.organization-table-wrap td { height: 46px; max-height: 46px; }
.organization-admin-page .organization-company-table th:nth-child(2), .organization-admin-page .organization-company-table td:nth-child(2), .organization-admin-page .organization-company-table th:nth-child(3), .organization-admin-page .organization-company-table td:nth-child(3) { text-align: center; width: 72px; }
.organization-admin-page .organization-company-table th:nth-child(4), .organization-admin-page .organization-company-table td:nth-child(4) { text-align: center; width: 88px; }
.organization-admin-page .organization-company-table th:last-child, .organization-admin-page .organization-company-table td:last-child { text-align: right; width: 110px; }
.organization-admin-page .organization-submission-table th:nth-child(4), .organization-admin-page .organization-submission-table td:nth-child(4) { text-align: center; width: 90px; }
.organization-admin-page .organization-submission-table th:last-child, .organization-admin-page .organization-submission-table td:last-child { text-align: right; width: 120px; }
.organization-table-wrap tbody tr:last-child td { border-bottom: 0; }
.organization-table-wrap .text-action { align-items: center; display: inline-flex; gap: 6px; white-space: nowrap; }
.organization-table-wrap .compact-button { min-height: 34px; }
.organization-list-pagination { margin-top: 8px; }
.organization-error { background: #fff4f2; border: 1px solid #f5c2bb; border-radius: 10px; color: #a3372c; margin: 14px 0; padding: 11px 14px; }
.organization-back { align-items: center; display: inline-flex; flex: 0 0 auto; gap: 5px; margin: 0; }
.organization-detail-title { flex: 1 1 auto; min-width: 0; }
.organization-detail-title h2 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.organization-company-detail .lead-detail-page-header { padding: 0 0 14px; }
.organization-company-detail .organization-header-actions button { min-height: 40px; white-space: nowrap; }
.organization-company-detail .organization-list-pagination { margin-top: 8px; }
.organization-status { border-radius: 999px; display: inline-block; font-size: 12px; padding: 4px 8px; }
.organization-status.submitted { background: #e8f7ef; color: #167044; }
.organization-status.draft { background: #fff4dc; color: #946518; }
@media (max-width: 640px) { .organization-admin-page { height: auto; min-height: 0; } .organization-admin-page.organization-company-selected { height: calc(100dvh - 50px); max-height: calc(100dvh - 50px); overflow-y: auto; overscroll-behavior: contain; } .organization-admin-page > .table-section { padding: 14px; } .organization-company-selected > .organization-company-detail { overflow: visible; } .organization-admin-header { align-items: flex-start; flex-wrap: wrap; } .organization-detail-title { flex: 1 1 100%; } .organization-detail-title h2 { white-space: normal; } .organization-header-actions { flex: 1 1 100%; flex-wrap: wrap; margin-left: 0; } .organization-header-actions button { flex: 1 1 190px; justify-content: center; } .organization-list-pagination { align-items: flex-start; flex-direction: column; } .organization-list-pagination .pagination-nav { flex-wrap: wrap; justify-content: flex-start; } }
</style>

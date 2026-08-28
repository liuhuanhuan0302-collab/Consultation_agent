import type { AnalyticsSummary, CaseStudy, ChannelSource, ExportBatch, GatewayConfig, Lead, LeadDetail, Question, QuestionModule, Report, ReportContactSettings, ScoreResponse, User } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers || {}) as Record<string, string>)
  };
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg || JSON.stringify(item)).join("；")
      : detail || `请求失败：${response.status}`;
    throw new ApiError(response.status, message);
  }
  return response.json();
}

async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(response.status, payload.detail || `导出失败：${response.status}`);
  }
  const disposition = response.headers.get("content-disposition") || "";
  const utf8Name = /filename\*=UTF-8''([^;]+)/i.exec(disposition)?.[1];
  const plainName = /filename="?([^";]+)"?/i.exec(disposition)?.[1];
  const filename = decodeURIComponent(utf8Name || plainName || fallbackName);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export type LeadQueryParams = {
  industry?: string;
  lead_level?: string;
  source_code?: string;
  created_from?: string;
  created_to?: string;
  view_status?: string;
  processing_status?: string;
  export_status?: string;
  sort?: string;
};

function leadQueryString(params: LeadQueryParams): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.set(key, value);
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  createSession: (sourceCode?: string) =>
    request<{ session_token: string }>("/api/public/sessions", {
      method: "POST",
      body: JSON.stringify({ source_code: sourceCode || "default", metadata: { href: window.location.href } })
    }),
  track: (event_name: string, session_token?: string | null, lead_id?: number | null, metadata?: Record<string, unknown>) =>
    request<{ message: string }>("/api/public/events", {
      method: "POST",
      body: JSON.stringify({ event_name, session_token, lead_id, metadata })
    }),
  questions: () => request<QuestionModule[]>("/api/public/questions"),
  submitLead: (payload: Record<string, unknown>) =>
    request<{ lead: Lead; submission_id: number }>("/api/public/leads", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  saveDraft: (submissionId: number, answers: { question_id: number; score: number }[], sessionToken: string) =>
    request<{ message: string }>(`/api/public/submissions/${submissionId}/draft`, {
      method: "PUT",
      headers: { "X-Session-Token": sessionToken },
      body: JSON.stringify({ answers })
    }),
  submitQuestionnaire: (submissionId: number, answers: { question_id: number; score: number }[], sessionToken: string) =>
    request<{ score: ScoreResponse; report: Report }>(`/api/public/submissions/${submissionId}/submit`, {
      method: "POST",
      headers: { "X-Session-Token": sessionToken },
      body: JSON.stringify({ answers })
    }),
  submissionReport: (submissionId: number, sessionToken: string) =>
    request<Report>(`/api/public/submissions/${submissionId}/report`, {
      headers: { "X-Session-Token": sessionToken }
    }),
  publicReport: (token: string) => request<Report>(`/api/public/reports/${token}`),
  regenerateReportForTesting: (token: string) =>
    request<Report>(`/api/public/reports/${token}/regenerate`, { method: "POST" }),
  login: (email: string, password: string) =>
    request<{ message: string }>("/api/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }),
  logout: () => request<{ message: string }>("/api/admin/auth/logout", { method: "POST" }),
  me: () => request<User>("/api/admin/me"),
  analytics: () => request<AnalyticsSummary>("/api/admin/analytics/summary"),
  leads: (params: LeadQueryParams = {}) => request<Lead[]>(`/api/admin/leads${leadQueryString(params)}`),
  leadDetail: (leadId: number) => request<LeadDetail>(`/api/admin/leads/${leadId}`),
  triggerLeadResearch: (leadId: number, force = false) =>
    request<{ status: string; message?: string }>(`/api/admin/leads/${leadId}/research${force ? "?force=true" : ""}`, {
      method: "POST"
    }),
  resumeReportDelivery: (leadId: number) =>
    request<{ message: string }>(`/api/admin/leads/${leadId}/resume-delivery`, { method: "POST" }),
  retryReportAttachmentDelivery: (leadId: number) =>
    request<{ message: string }>(`/api/admin/leads/${leadId}/retry-attachment-delivery`, { method: "POST" }),
  regenerateLeadReport: (leadId: number) =>
    request<{ status: string; message: string }>(`/api/admin/leads/${leadId}/regenerate-report`, { method: "POST" }),
  updateLeadDiagnosticEmail: (leadId: number, email: string) =>
    request<{ message: string }>(`/api/admin/leads/${leadId}/diagnostic-email`, {
      method: "PUT",
      body: JSON.stringify({ email })
    }),
  deleteLead: (leadId: number) =>
    request<{ message: string }>(`/api/admin/leads/${leadId}`, { method: "DELETE" }),
  leadWordExport: (leadId: number) => downloadFile(`/api/admin/leads/${leadId}/export/word`, `lead-${leadId}.docx`),
  leadsExport: (params: LeadQueryParams = {}) => downloadFile(`/api/admin/leads/export${leadQueryString(params)}`, "leads.csv"),
  exportUnexportedLeads: () =>
    request<{ batch_id: number | null; rows_count: number; message: string }>("/api/admin/leads/export-unexported", {
      method: "POST"
    }),
  exportBatches: () => request<ExportBatch[]>("/api/admin/leads/export-batches"),
  downloadExportBatch: (batchId: number) => downloadFile(`/api/admin/leads/export-batches/${batchId}/download`, `export-batch-${batchId}.csv`),
  reportContactSettings: () => request<ReportContactSettings>("/api/admin/system-settings/report-contact"),
  saveReportContactSettings: (payload: Record<string, unknown>) =>
    request<ReportContactSettings>("/api/admin/system-settings/report-contact", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  gatewayConfig: () => request<GatewayConfig>("/api/admin/api-gateway"),
  saveSearchConfig: (payload: Record<string, unknown>) =>
    request<GatewayConfig>("/api/admin/api-gateway/search", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  saveLlmConfig: (payload: Record<string, unknown>) =>
    request<GatewayConfig>("/api/admin/api-gateway/llm", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  testSearchConfig: (query: string, overrides: Record<string, unknown>) =>
    request<{ ok: boolean; query?: string; result_count?: number; elapsed_ms?: number; first_results?: string[]; error?: string }>("/api/admin/api-gateway/test-search", {
      method: "POST",
      body: JSON.stringify({ query, ...overrides })
    }),
  testLlmConfig: (overrides: Record<string, unknown>) =>
    request<{ ok: boolean; model?: string; elapsed_ms?: number; reply?: string; error?: string }>("/api/admin/api-gateway/test-llm", {
      method: "POST",
      body: JSON.stringify(overrides)
    }),
  adminQuestions: () => request<QuestionModule[]>("/api/admin/questions"),
  createQuestionModule: (payload: Record<string, unknown>) =>
    request<QuestionModule>("/api/admin/modules", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteQuestionModule: (moduleId: number) =>
    request<{ message: string }>(`/api/admin/modules/${moduleId}`, { method: "DELETE" }),
  createQuestion: (payload: Record<string, unknown>) =>
    request<Question>("/api/admin/questions", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteQuestion: (questionId: number) =>
    request<{ message: string }>(`/api/admin/questions/${questionId}`, { method: "DELETE" }),
  cases: () => request<CaseStudy[]>("/api/admin/cases"),
  createCase: (payload: Record<string, unknown>) =>
    request<CaseStudy>("/api/admin/cases", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  users: () => request<User[]>("/api/admin/users"),
  createUser: (payload: Record<string, unknown>) =>
    request<User>("/api/admin/users", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  channels: () => request<ChannelSource[]>("/api/admin/channels"),
  createChannel: (payload: Record<string, unknown>) =>
    request<ChannelSource>("/api/admin/channels", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteChannel: (channelId: number) =>
    request<{ message: string }>(`/api/admin/channels/${channelId}`, {
      method: "DELETE"
    })
};

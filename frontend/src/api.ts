import type { AnalyticsSummary, CaseStudy, ChannelSource, Lead, LeadDetail, QuestionModule, Report, ScoreResponse, User } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("admin_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers || {}) as Record<string, string>)
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(response.status, payload.detail || `请求失败：${response.status}`);
  }
  return response.json();
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
  saveDraft: (submissionId: number, answers: { question_id: number; score: number }[]) =>
    request<{ message: string }>(`/api/public/submissions/${submissionId}/draft`, {
      method: "PUT",
      body: JSON.stringify({ answers })
    }),
  submitQuestionnaire: (submissionId: number, answers: { question_id: number; score: number }[]) =>
    request<{ score: ScoreResponse; report: Report }>(`/api/public/submissions/${submissionId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers })
    }),
  submissionReport: (submissionId: number, sessionToken: string) =>
    request<Report>(`/api/public/submissions/${submissionId}/report?session_token=${encodeURIComponent(sessionToken)}`),
  latestSessionReport: (sessionToken: string) =>
    request<Report>(`/api/public/sessions/report?session_token=${encodeURIComponent(sessionToken)}`),
  publicReport: (token: string) => request<Report>(`/api/public/reports/${token}`),
  emailReport: (token: string, email: string) =>
    request<{ message: string }>(`/api/public/reports/${token}/email`, {
      method: "POST",
      body: JSON.stringify({ email })
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/api/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }),
  me: () => request<User>("/api/admin/me"),
  analytics: () => request<AnalyticsSummary>("/api/admin/analytics/summary"),
  leads: () => request<Lead[]>("/api/admin/leads"),
  leadDetail: (leadId: number) => request<LeadDetail>(`/api/admin/leads/${leadId}`),
  adminQuestions: () => request<QuestionModule[]>("/api/admin/questions"),
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

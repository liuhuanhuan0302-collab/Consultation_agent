export type Lead = {
  id: number;
  session_token: string;
  company_name: string | null;
  city: string | null;
  industry: string | null;
  company_size: string | null;
  annual_revenue: string | null;
  contact_name: string | null;
  position: string | null;
  phone: string | null;
  email: string | null;
  wechat: string | null;
  ai_focus: string | null;
  source_code: string | null;
  lead_level: string;
  priority_strategy: string | null;
  demand_summary: string | null;
  created_at: string;
  updated_at: string;
  last_activity_at: string | null;
  view_status: string;
  first_viewed_at: string | null;
  first_viewed_by: string | null;
  processing_status: string;
  processing_note: string | null;
  export_status: string;
  first_exported_at: string | null;
  last_exported_at: string | null;
};

export type ExportBatch = {
  id: number;
  created_at: string;
  rows_count: number;
  file_name: string;
  exported_by: string | null;
  filters_summary: string | null;
};

export type Question = {
  id: number;
  code: string;
  dimension: string | null;
  text: string;
  option_text: string | null;
  sort_order: number;
  max_score: number;
};

export type QuestionModule = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  max_score: number;
  sort_order: number;
  questions: Question[];
};

export type DimensionScore = {
  module_code: string;
  module_name: string;
  raw_score: number;
  max_score: number;
  score_rate: number;
  risk_level: string;
};

export type CoreFinding = {
  finding: string;
  evidence: string;
  meaning: string;
};

export type ScoreResponse = {
  submission_id: number;
  total_score: number;
  max_score: number;
  score_rate: number;
  risk_level: string;
  low_dimensions: DimensionScore[];
  dimensions: DimensionScore[];
};

export type Report = {
  id: number;
  public_token: string;
  status: string;
  title: string;
  html_content: string;
  created_at: string;
  score?: {
    total: number;
    max_score: number;
    score_rate: number;
    risk_level: string;
  };
  dimensions?: DimensionScore[];
  low_dimensions?: DimensionScore[];
  core_findings?: CoreFinding[];
  customer_classification?: {
    lead_level?: string;
    priority_strategy?: string;
    demand_summary?: string;
  };
  delivery_status?: string | null;
  queue_position?: number | null;
  delivery_error?: string | null;
  generation_error?: string | null;
};

export type CaseStudy = {
  id: number;
  title: string;
  industry: string;
  function_area: string;
  module_code: string;
  maturity: string;
  roi_level: string;
  difficulty: string;
  description: string;
  expected_benefit: string;
  priority_tag: string;
  is_active: boolean;
  created_at: string;
};

export type ChannelSource = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
};

export type AnalyticsBucket = {
  label: string;
  count: number;
};

export type AnalyticsFunnelStep = AnalyticsBucket & {
  rate: number;
};

export type AnalyticsSummary = {
  visit_uv: number;
  started_count: number;
  info_completed_count: number;
  questionnaire_completed_count: number;
  report_generated_count: number;
  report_claimed_count: number;
  high_intent_leads: number;
  lead_count: number;
  questionnaire_completion_rate: number;
  funnel: AnalyticsFunnelStep[];
  hourly_questionnaire_counts: AnalyticsBucket[];
  lead_level_distribution: AnalyticsBucket[];
  industry_distribution: AnalyticsBucket[];
};

export type CompanyResearchSubsection = {
  title: string;
  content: string;
};

export type CompanyResearchValue = string | CompanyResearchSubsection[];

export type CompanyResearch = {
  company_name?: string;
  company_overview?: CompanyResearchValue;
  revenue_scale?: CompanyResearchValue;
  products?: CompanyResearchValue;
  industry_characteristics?: CompanyResearchValue;
  development_status?: CompanyResearchValue;
  challenges?: CompanyResearchValue;
  ai_opportunities?: CompanyResearchValue;
  analysis?: CompanyResearchValue;
  sources?: { title: string; url: string }[];
  researched_at?: string;
};

export type GatewayConfig = {
  search_provider: "bocha" | "serpapi" | "deepseek" | "custom";
  search_api_key: string;
  search_base_url: string | null;
  search_timeout_seconds: number;
  search_max_results: number;
  search_model: string | null;
  llm_api_key: string;
  llm_base_url: string | null;
  llm_model: string | null;
  key_reentry_required: boolean;
  updated_by: string | null;
  updated_at: string | null;
};

export type ReportContactSettings = {
  contact_name: string;
  phone: string;
  wechat: string;
  email: string;
  updated_by: string | null;
  updated_at: string | null;
};

export type User = {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type LeadDetail = {
  lead: Lead;
  submission: {
    id: number;
    status: string;
    total_score: number | null;
    max_score: number;
    score_rate: number | null;
    risk_level: string | null;
    created_at: string;
    submitted_at: string | null;
    dimensions: DimensionScore[];
  } | null;
  report: {
    id: number;
    public_token: string;
    title: string;
    status: string;
    research_status: string;
    research_started_at: string | null;
    research_completed_at: string | null;
    research_elapsed_seconds: number | null;
    generation_started_at: string | null;
    generation_completed_at: string | null;
    generation_elapsed_seconds: number | null;
    pdf_status: string;
    pdf_started_at: string | null;
    pdf_completed_at: string | null;
    pdf_elapsed_seconds: number | null;
    html_content: string;
    summary: Record<string, unknown>;
    company_research: CompanyResearch | null;
    generation_error: string | null;
    created_at: string;
    advisor_messages: {
      role: string;
      purpose: string;
      content: string;
      model_vendor: string | null;
      model_name: string | null;
      created_at: string;
    }[];
  } | null;
  delivery: {
    status: "queued" | "processing" | "sent" | "failed";
    recipient_email: string;
    last_error: string | null;
    sent_at: string | null;
    started_at: string | null;
    updated_at: string | null;
    elapsed_seconds: number | null;
    queue_position: number | null;
  } | null;
};

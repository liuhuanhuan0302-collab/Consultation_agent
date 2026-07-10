export type Lead = {
  id: number;
  session_token: string;
  company_name: string | null;
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
  customer_classification?: {
    lead_level?: string;
    priority_strategy?: string;
    demand_summary?: string;
  };
  advisor_messages?: {
    role: string;
    purpose: string;
    content: string;
    model_vendor: string | null;
    model_name: string | null;
    created_at: string;
  }[];
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

export type AnalyticsSummary = {
  visit_uv: number;
  started_count: number;
  info_completed_count: number;
  questionnaire_completed_count: number;
  report_generated_count: number;
  report_claimed_count: number;
  high_intent_leads: number;
  lead_count: number;
};

export type User = {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

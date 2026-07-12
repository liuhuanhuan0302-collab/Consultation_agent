"""
Pydantic 请求/响应模型 — FastAPI 自动生成 OpenAPI 文档。
model_config = ConfigDict(from_attributes=True) 表示可从 ORM 对象直接转换。
"""

from datetime import datetime
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Role


# ── 认证 ──────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    """登录成功返回的 JWT token"""
    access_token: str = Field(description="JWT 令牌，后续请求放在 Authorization: Bearer 头中")
    token_type: str = Field(default="bearer", description="令牌类型，固定为 bearer")


class LoginRequest(BaseModel):
    """后台登录请求"""
    email: EmailStr = Field(description="登录邮箱")
    password: str = Field(description="登录密码")


# ── 用户管理 ──────────────────────────────────────────────────────
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    role: Role
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    """创建后台用户"""
    email: EmailStr = Field(description="登录邮箱")
    name: str = Field(description="姓名")
    role: Role = Field(description="角色：admin/operator/sales/consultant")
    password: str = Field(min_length=8, description="初始密码，不少于 8 位")


# ── 会话 & 线索 ───────────────────────────────────────────────────
class SessionCreate(BaseModel):
    """创建匿名会话"""
    source_code: str | None = Field(default=None, description="来源渠道编码，用于追踪扫码入口")
    metadata: dict[str, Any] | None = Field(default=None, description="额外元数据，前端可传页面 URL 等")


class SessionResponse(BaseModel):
    """会话创建结果"""
    session_token: str = Field(description="32 位十六进制会话令牌，前端存入 localStorage")


class LeadCreate(BaseModel):
    """客户提交企业信息 — 创建/更新线索"""
    session_token: str | None = Field(default=None, description="会话令牌，关联匿名身份")
    company_name: str = Field(min_length=1, max_length=255, description="企业全称")
    industry: str = Field(min_length=1, max_length=120, description="所属行业，如 制造业/消费品/医疗健康")
    company_size: str = Field(min_length=1, max_length=80, description="企业规模，如 200-1000人")
    annual_revenue: str | None = Field(default=None, description="年营收区间，如 1-5亿")
    contact_name: str = Field(min_length=1, max_length=80, description="联系人姓名")
    position: str = Field(min_length=1, max_length=120, description="联系人职位")
    phone: str | None = Field(default=None, description="手机号，与微信至少填一项")
    email: EmailStr = Field(description="接收诊断报告的邮箱")
    wechat: str | None = Field(default=None, description="微信号，与手机至少填一项")
    ai_focus: str | None = Field(default=None, description="当前关注的 AI 转型方向")
    privacy_accepted: bool = Field(description="是否同意隐私政策与联系授权，必须为 true")
    contact_authorized: bool = Field(description="是否授权后续联系")
    source_code: str | None = Field(default=None, description="来源渠道编码")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        phone = value.strip()
        if not re.fullmatch(r"1[3-9]\d{9}", phone):
            raise ValueError("请输入正确的 11 位手机号")
        return phone


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_token: str
    company_name: str | None
    industry: str | None
    company_size: str | None
    annual_revenue: str | None
    contact_name: str | None
    position: str | None
    phone: str | None
    email: EmailStr | None
    wechat: str | None
    ai_focus: str | None
    source_code: str | None
    lead_level: str = Field(description="线索等级：low=低意向 / medium=中意向 / high=高意向")
    priority_strategy: str | None = Field(default=None, description="建议打法：闪电战/攻坚战/升维战")
    demand_summary: str | None = Field(default=None, description="客户当前诉求摘要")
    created_at: datetime


class LeadCreatedResponse(BaseModel):
    """企业信息提交成功 — 返回线索 + 答题提交 ID"""
    lead: LeadResponse
    submission_id: int = Field(description="答题提交 ID，后续答题和提交都要用")


# ── 题库 ──────────────────────────────────────────────────────────
class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str = Field(description="题目编码，如 Q1")
    dimension: str | None = Field(description="评估维度，如 用户洞察")
    text: str = Field(description="题目文本")
    option_text: str | None = Field(description="0-4 量表描述，分号分隔，如 0=完全没有；1=...")
    sort_order: int
    max_score: int = Field(description="本题最高分，0-4")


class ModuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str = Field(description="模块编码，M01-M10")
    name: str = Field(description="模块名称")
    description: str | None = Field(description="模块简介")
    max_score: int = Field(description="本模块满分")
    sort_order: int
    questions: list[QuestionRead] = Field(default_factory=list, description="模块下题目列表")


class QuestionUpsert(BaseModel):
    """新增或更新题目 — code 在模块内已存在则更新"""
    module_code: str = Field(description="所属模块编码")
    code: str = Field(description="题目编码，模块内唯一")
    dimension: str | None = Field(default=None, description="评估维度标签")
    text: str = Field(description="题目文本")
    option_text: str | None = Field(default=None, description="0-4 量表描述，格式：0=完全没有；1=...")
    sort_order: int = Field(description="排序序号")
    max_score: int = Field(default=4, ge=1, le=4, description="本题分值，1-4")
    is_active: bool = Field(default=True, description="是否启用")


class ModuleUpsert(BaseModel):
    """新增或更新模块 — code 已存在则更新"""
    code: str = Field(description="模块编码，如 M01")
    name: str = Field(description="模块名称")
    description: str | None = Field(default=None, description="模块简介")
    max_score: int = Field(ge=1, description="模块满分，≥1")
    sort_order: int = Field(default=0, description="排序序号")
    is_active: bool = Field(default=True, description="是否启用")


# ── 答题 & 评分 ──────────────────────────────────────────────────
class AnswerInput(BaseModel):
    """单题答案"""
    question_id: int = Field(description="题目 ID")
    score: int = Field(ge=0, le=4, description="得分，0-4")


class DraftSaveRequest(BaseModel):
    """保存草稿 — 可随时保存部分答案"""
    answers: list[AnswerInput] = Field(description="已答题的答案列表，未答的题目可不提交")


class SubmitQuestionnaireRequest(BaseModel):
    """提交全部问卷 — 必须包含全部 68 题"""
    answers: list[AnswerInput] = Field(description="全部 68 题的答案，每题 score 范围 0-4")


class DimensionScoreRead(BaseModel):
    """单个维度的评分结果"""
    module_code: str = Field(description="模块编码")
    module_name: str = Field(description="模块名称")
    raw_score: int = Field(description="实际得分")
    max_score: int = Field(description="满分")
    score_rate: float = Field(description="得分率，0-1")
    risk_level: str = Field(description="风险等级：高风险/较弱/良好/优秀")


class ScoreResponse(BaseModel):
    """评分结果 — 含总分 + 10 维度详情 + 最薄弱 3 维度"""
    submission_id: int
    total_score: int = Field(description="总分，满分 260")
    max_score: int = Field(description="总分上限，固定 260")
    score_rate: float = Field(description="综合得分率，0-1")
    risk_level: str = Field(description="综合风险等级")
    low_dimensions: list[DimensionScoreRead] = Field(description="得分率最低的 3 个维度，优先改善方向")
    dimensions: list[DimensionScoreRead] = Field(description="全部 10 个维度评分明细")


# ── 报告 ──────────────────────────────────────────────────────────
class AiMessageRead(BaseModel):
    """模型对话记录，用于复盘 AI 基于什么输入生成了什么建议"""
    role: str = Field(description="user=发送给模型的上下文 / assistant=模型返回")
    purpose: str = Field(description="用途，如 report_advisor")
    content: str = Field(description="消息正文")
    model_vendor: str | None = Field(default=None, description="模型供应商")
    model_name: str | None = Field(default=None, description="模型名称")
    created_at: datetime


class ReportRead(BaseModel):
    """诊断报告"""
    id: int
    public_token: str = Field(description="公开访问 token，用于分享链接")
    status: str = Field(description="generated=AI生成 / fallback=模板生成 / failed=失败")
    title: str = Field(description="报告标题")
    html_content: str = Field(description="完整 HTML 报告内容")
    model_vendor: str = Field(description="AI 模型供应商，默认 deepseek")
    model_name: str | None = Field(description="使用的 AI 模型名称")
    created_at: datetime
    advisor_messages: list[AiMessageRead] = Field(default_factory=list, description="与本报告相关的大模型对话记录")


class SubmitResponse(BaseModel):
    """问卷提交结果 — 包含评分 + 报告"""
    score: ScoreResponse = Field(description="评分结果")
    report: ReportRead = Field(description="诊断报告")


# ── 案例 ──────────────────────────────────────────────────────────
class CaseStudyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str = Field(description="案例标题")
    industry: str = Field(description="适用行业，通用表示所有行业")
    function_area: str = Field(description="职能方向，如 客户服务")
    module_code: str = Field(description="匹配的模块编码")
    maturity: str = Field(description="成熟度：MVP/已落地/规模化")
    roi_level: str = Field(description="ROI 等级：high/medium/low")
    difficulty: str = Field(description="实施难度：high/medium/low")
    description: str = Field(description="案例描述")
    expected_benefit: str = Field(description="预期收益")
    priority_tag: str = Field(description="优先级标签：闪电战/攻坚战/升维战")
    is_active: bool
    created_at: datetime


class CaseStudyCreate(BaseModel):
    """创建案例 — 用于诊断报告中的场景推荐"""
    title: str = Field(description="案例标题")
    industry: str = Field(description="适用行业")
    function_area: str = Field(description="职能方向")
    module_code: str = Field(description="匹配的模块编码")
    maturity: str = Field(default="MVP", description="成熟度")
    roi_level: str = Field(default="medium", description="ROI 等级")
    difficulty: str = Field(default="medium", description="实施难度")
    description: str = Field(description="案例描述")
    expected_benefit: str = Field(description="预期收益")
    priority_tag: str = Field(default="攻坚战", description="优先级标签")
    is_active: bool = Field(default=True, description="是否启用")


# ── 统计 ──────────────────────────────────────────────────────────
class AnalyticsBucket(BaseModel):
    label: str
    count: int


class AnalyticsFunnelStep(BaseModel):
    label: str
    count: int
    rate: float


class AnalyticsSummary(BaseModel):
    """后台统计看板数据 — 展示客户转化漏斗"""
    visit_uv: int = Field(description="独立访客数")
    started_count: int = Field(description="点击'开始自测'人数")
    info_completed_count: int = Field(description="完成企业信息填写人数")
    questionnaire_completed_count: int = Field(description="完成全部 68 题人数")
    report_generated_count: int = Field(description="成功生成报告数")
    report_claimed_count: int = Field(description="下载 PDF 数")
    high_intent_leads: int = Field(description="高意向线索数：有联系方式+至少 2 个维度得分率 < 50%")
    lead_count: int = Field(description="线索总数")
    questionnaire_completion_rate: float = Field(default=0, description="答题完成率：问卷完成 / 信息完成")
    funnel: list[AnalyticsFunnelStep] = Field(default_factory=list, description="转化漏斗")
    hourly_questionnaire_counts: list[AnalyticsBucket] = Field(default_factory=list, description="按小时统计的问卷完成人数")
    lead_level_distribution: list[AnalyticsBucket] = Field(default_factory=list, description="线索等级分布")
    strategy_distribution: list[AnalyticsBucket] = Field(default_factory=list, description="打法分布")
    industry_distribution: list[AnalyticsBucket] = Field(default_factory=list, description="行业分布")


# ── 埋点 ──────────────────────────────────────────────────────────
class TrackEventRequest(BaseModel):
    """用户行为埋点事件"""
    session_token: str | None = Field(default=None, description="会话令牌")
    lead_id: int | None = Field(default=None, description="线索 ID")
    event_name: str = Field(description="事件名称：enter_site/click_start/submit_customer_info/submit_questionnaire/view_report_summary/claim_full_report")
    metadata: dict[str, Any] | None = Field(default=None, description="额外事件数据")


# ── 渠道 ──────────────────────────────────────────────────────────
class ChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str = Field(description="渠道编码，如 wechat_mp")
    name: str = Field(description="渠道名称")
    description: str | None = Field(default=None, description="描述")
    is_active: bool
    created_at: datetime


class ChannelUpsert(BaseModel):
    """新增或更新渠道 — code 已存在则更新"""
    code: str = Field(description="渠道编码，用于 URL 参数 ?source={code}")
    name: str = Field(description="渠道名称，如 微信公众号")
    description: str | None = Field(default=None, description="描述")
    is_active: bool = Field(default=True, description="是否启用")


# ── 通用 ──────────────────────────────────────────────────────────
class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str = Field(description="操作结果消息")


class ReportEmailRequest(BaseModel):
    """发送报告 PDF 到邮箱"""
    email: EmailStr = Field(description="接收报告的邮箱地址")

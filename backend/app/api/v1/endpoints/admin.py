"""
管理后台接口 — 所有接口需要 JWT Bearer Token 鉴权。

角色权限：
  admin       → 所有接口（包括创建用户）
  operator    → 题库/案例/渠道 CRUD + 查看线索/报告/统计
  sales       → 查看线索（含导出）+ 报告 + 统计
  consultant  → 查看线索 + 报告 + 统计

token 获取：POST /api/admin/auth/login
token 有效期：720 分钟（12 小时）
使用方式：请求头 Authorization: Bearer {token}
"""

import csv
import json
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AiConversationMessage,
    CaseStudy,
    ChannelSource,
    CompanyLead,
    ExportLog,
    Question,
    QuestionModule,
    Report,
    ReportStatus,
    TrackingEvent,
    User,
)
from app.schemas import (
    AnalyticsSummary,
    CaseStudyCreate,
    CaseStudyRead,
    ChannelRead,
    ChannelUpsert,
    LeadResponse,
    LoginRequest,
    ModuleRead,
    ModuleUpsert,
    QuestionRead,
    QuestionUpsert,
    TokenResponse,
    UserCreate,
    UserRead,
)
from app.repositories.case_repo import list_case_studies
from app.repositories.consult_repo import (
    get_event_counts_map,
    get_high_intent_lead_count,
    get_report_by_id,
    get_report_generated_count,
    get_total_lead_count,
    get_visit_uv,
    list_all_leads,
    list_leads,
    list_recent_events,
)
from app.repositories.questionnaire_repo import (
    active_modules_with_questions,
    get_module_by_code,
    get_question_by_module_and_code,
)
from app.repositories.qr_code_repo import get_channel_by_code, list_channels as list_channel_sources
from app.repositories.user_repo import get_active_user_by_email, get_user_by_email, list_users as list_user_accounts
from app.utils.logging_utils import write_operation_log
from app.utils.auth import AdminOnly, ContentManager, LeadExporter, LeadViewer, ReportViewer, get_current_user
from app.utils.security import create_access_token, hash_password, verify_password


router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ══════════════════════════════════════════════════════════════════
# 3.1 后台登录
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/auth/login
# 功能：后台用户登录，校验邮箱密码，返回 JWT access_token
#       密码使用 pbkdf2_sha256 哈希校验
# 限流：同一 IP 每分钟最多 5 次（防暴力破解）
# 鉴权：无
# 请求：{ email: string, password: string }
# 返回：{ access_token: string, token_type: "bearer" }
# 错误：401 "账号或密码错误"
@router.post("/api/admin/auth/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def admin_login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = get_active_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    return TokenResponse(access_token=create_access_token(str(user.id), {"role": user.role.value if hasattr(user.role, "value") else user.role}))


# ══════════════════════════════════════════════════════════════════
# 3.2 获取当前用户信息
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/me
# 功能：校验 token 有效性，返回当前登录用户信息
#       前端用来判断是否已登录、角色权限是什么
# 鉴权：Bearer Token（任意角色均可）
# 返回：{ id, email, name, role, is_active, created_at }
@router.get("/api/admin/me", response_model=UserRead)
def admin_me(user: User = Depends(get_current_user)) -> User:
    return user


# ══════════════════════════════════════════════════════════════════
# 3.3 创建后台用户
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/users
# 功能：管理员创建新的后台用户
# 鉴权：admin 角色
# 请求：{ email*, name*, role*, password* }  password 最少 8 位
#       role: "admin" | "operator" | "sales" | "consultant"
# 返回：{ id, email, name, role, is_active, created_at }
# 错误：409 "Email already exists"
@router.post("/api/admin/users", response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> User:
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="Email already exists")
    created = User(email=payload.email, name=payload.name, role=payload.role.value, password_hash=hash_password(payload.password))
    db.add(created)
    write_operation_log(db, user, "create_user", "user", payload.email)
    db.commit()
    db.refresh(created)
    return created


# ══════════════════════════════════════════════════════════════════
# 3.4 列出后台用户
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/users
# 功能：管理员查看所有后台用户列表
# 鉴权：admin 角色
# 返回：UserRead[] 数组
@router.get("/api/admin/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> list[User]:
    return list_user_accounts(db)


# ══════════════════════════════════════════════════════════════════
# 3.5 线索列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/leads
# 功能：查看所有客户线索，最多 500 条
#       支持按 行业 / 线索等级 / 来源渠道 筛选
# 鉴权：admin / operator / sales / consultant
# 查询参数（均可选）：
#       ?industry=制造业&lead_level=high&source_code=wechat_mp
# 返回：LeadResponse[] 数组（按创建时间倒序）
@router.get("/api/admin/leads", response_model=list[LeadResponse])
def admin_list_leads(
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(LeadViewer),
) -> list[CompanyLead]:
    return list_leads(db, industry=industry, lead_level=lead_level, source_code=source_code)


# ══════════════════════════════════════════════════════════════════
# 3.6 导出线索 CSV
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/leads/export
# 功能：导出全部线索为 CSV 文件（最多 10 万条）
#       CSV 列：公司, 行业, 规模, 联系人, 职位, 手机, 微信, 来源, 线索等级, 创建时间
# 鉴权：admin / operator / sales
# 返回：CSV 文件下载（Content-Type: text/csv）
#       文件名：leads.csv
@router.get("/api/admin/leads/export")
def export_leads(db: Session = Depends(get_db), user: User = Depends(LeadExporter)) -> StreamingResponse:
    leads = list_leads(db, limit=100000)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["公司", "行业", "规模", "联系人", "职位", "手机", "邮箱", "微信", "来源", "线索等级", "建议打法", "诉求摘要", "创建时间"])
    for lead in leads:
        writer.writerow(
            [
                lead.company_name,
                lead.industry,
                lead.company_size,
                lead.contact_name,
                lead.position,
                lead.phone,
                lead.email,
                lead.wechat,
                lead.source_code,
                lead.lead_level,
                lead.priority_strategy,
                lead.demand_summary,
                lead.created_at.isoformat(),
            ]
        )
    db.add(ExportLog(user_id=user.id, export_type="leads", filters_json=None, rows_count=len(leads)))
    write_operation_log(db, user, "export_leads", "lead", "all", {"rows": len(leads)})
    db.commit()
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


# ══════════════════════════════════════════════════════════════════
# 3.7 查看报告详情
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/reports/{report_id}
# 功能：后台查看某份诊断报告的完整内容（HTML + 结构化摘要 JSON）
#       注意：report_id 是数字 ID，不是 public_token
# 鉴权：admin / operator / sales / consultant
# 请求：路径参数 report_id (int)
# 返回：{ id, public_token, title, status, html_content, summary, created_at }
@router.get("/api/admin/reports/{report_id}")
def admin_get_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(ReportViewer)) -> dict:
    report = get_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    advisor_messages = (
        db.query(AiConversationMessage)
        .filter(AiConversationMessage.report_id == report.id)
        .order_by(AiConversationMessage.created_at.asc())
        .all()
    )
    return {
        "id": report.id,
        "public_token": report.public_token,
        "title": report.title,
        "status": report.status,
        "html_content": report.html_content,
        "summary": json.loads(report.summary_json or "{}"),
        "advisor_messages": [
            {
                "role": message.role,
                "purpose": message.purpose,
                "content": message.content,
                "model_vendor": message.model_vendor,
                "model_name": message.model_name,
                "created_at": message.created_at,
            }
            for message in advisor_messages
        ],
        "created_at": report.created_at,
    }


# ══════════════════════════════════════════════════════════════════
# 3.8 查看题库
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/questions
# 功能：查看所有模块和题目（含非激活题）
# 鉴权：admin / operator / sales / consultant
# 返回：ModuleRead[] 数组
@router.get("/api/admin/questions", response_model=list[ModuleRead])
def admin_list_questions(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[QuestionModule]:
    return active_modules_with_questions(db)


# ══════════════════════════════════════════════════════════════════
# 3.9 新增/更新模块
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/modules
# 功能：创建或更新题库模块（code 已存在则更新，不存在则新增）
# 鉴权：admin / operator
# 请求：{ code*, name*, description?, max_score*, sort_order*, is_active* }
# 返回：模块对象
@router.post("/api/admin/modules", response_model=ModuleRead)
def upsert_module(payload: ModuleUpsert, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> QuestionModule:
    module = get_module_by_code(db, payload.code)
    if not module:
        module = QuestionModule(code=payload.code)
        db.add(module)
    module.name = payload.name
    module.description = payload.description
    module.max_score = payload.max_score
    module.sort_order = payload.sort_order
    module.is_active = payload.is_active
    write_operation_log(db, user, "upsert_module", "question_module", payload.code)
    db.commit()
    db.refresh(module)
    return module


# ══════════════════════════════════════════════════════════════════
# 3.10 新增/更新题目
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/questions
# 功能：在指定模块下创建或更新题目
#       code 在模块内已存在则更新，不存在则新增
# 鉴权：admin / operator
# 请求：{ module_code*, code*, dimension?, text*, option_text?,
#          sort_order*, max_score*(1-4), is_active* }
# 返回：题目对象
# 错误：404 如果 module_code 不存在
@router.post("/api/admin/questions", response_model=QuestionRead)
def upsert_question(payload: QuestionUpsert, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> Question:
    module = get_module_by_code(db, payload.module_code)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    question = get_question_by_module_and_code(db, module.id, payload.code)
    if not question:
        question = Question(module_id=module.id, code=payload.code)
        db.add(question)
    question.text = payload.text
    question.dimension = payload.dimension
    question.option_text = payload.option_text
    question.sort_order = payload.sort_order
    question.max_score = payload.max_score
    question.is_active = payload.is_active
    write_operation_log(db, user, "upsert_question", "question", payload.code)
    db.commit()
    db.refresh(question)
    return question


# ══════════════════════════════════════════════════════════════════
# 3.11 案例列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/cases
# 功能：查看所有 AI 场景案例
# 鉴权：admin / operator / sales / consultant
# 返回：CaseStudyRead[] 数组
@router.get("/api/admin/cases", response_model=list[CaseStudyRead])
def list_cases(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[CaseStudy]:
    return list_case_studies(db)


# ══════════════════════════════════════════════════════════════════
# 3.12 新增案例
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/cases
# 功能：创建新的 AI 场景案例（用于报告中的推荐匹配）
#       案例按 module_code 匹配低分维度，按 industry 匹配客户行业
# 鉴权：admin / operator
# 请求：{ title*, industry*, function_area*, module_code*,
#          maturity?, roi_level?, difficulty?, description*,
#          expected_benefit*, priority_tag?, is_active? }
# 返回：案例对象
@router.post("/api/admin/cases", response_model=CaseStudyRead)
def create_case(payload: CaseStudyCreate, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> CaseStudy:
    case = CaseStudy(**payload.model_dump())
    db.add(case)
    write_operation_log(db, user, "create_case", "case", payload.title)
    db.commit()
    db.refresh(case)
    return case


# ══════════════════════════════════════════════════════════════════
# 3.13 渠道列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/channels
# 功能：查看所有推广渠道
#       渠道二维码：GET /api/public/channels/{code}/qr
# 鉴权：admin / operator / sales / consultant
# 返回：ChannelRead[] 数组
@router.get("/api/admin/channels", response_model=list[ChannelRead])
def list_channels(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[ChannelSource]:
    return list_channel_sources(db)


# ══════════════════════════════════════════════════════════════════
# 3.14 新增渠道
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/channels
# 功能：创建或更新推广渠道
#       创建后可调用 GET /api/public/channels/{code}/qr 获取二维码图片
# 鉴权：admin / operator
# 请求：{ code*, name*, description?, is_active* }
# 返回：渠道对象
@router.post("/api/admin/channels", response_model=ChannelRead)
def upsert_channel(payload: ChannelUpsert, db: Session = Depends(get_db), user: User = Depends(ContentManager)) -> ChannelSource:
    channel = get_channel_by_code(db, payload.code)
    if not channel:
        channel = ChannelSource(code=payload.code)
        db.add(channel)
    channel.name = payload.name
    channel.description = payload.description
    channel.is_active = payload.is_active
    write_operation_log(db, user, "upsert_channel", "channel_source", payload.code)
    db.commit()
    db.refresh(channel)
    return channel


# ══════════════════════════════════════════════════════════════════
# 3.15 统计分析看板
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/analytics/summary
# 功能：后台首页统计看板，展示转化漏斗
# 鉴权：admin / operator / sales / consultant
# 返回：{
#         visit_uv         → 独立访客数（进入页面）
#         started_count    → 点击"开始自测"人数
#         info_completed_count    → 完成企业信息填写
#         questionnaire_completed_count → 完成全部 68 题
#         report_generated_count     → 成功生成报告
#         report_claimed_count       → 下载 PDF 数
#         high_intent_leads → 高意向线索（有联系方式+至少 2 个低分维度）
#         lead_count        → 线索总数
#       }
@router.get("/api/admin/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> AnalyticsSummary:
    event_counts = get_event_counts_map(db)
    return AnalyticsSummary(
        visit_uv=get_visit_uv(db),
        started_count=event_counts.get("click_start", 0),
        info_completed_count=event_counts.get("submit_customer_info", 0),
        questionnaire_completed_count=event_counts.get("submit_questionnaire", 0),
        report_generated_count=get_report_generated_count(db),
        report_claimed_count=event_counts.get("claim_full_report", 0),
        high_intent_leads=get_high_intent_lead_count(db),
        lead_count=get_total_lead_count(db),
    )


# ══════════════════════════════════════════════════════════════════
# 3.16 埋点事件列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/events
# 功能：查看最近 200 条用户行为埋点事件
# 鉴权：admin / operator / sales / consultant
# 返回：[{ id, session_token, lead_id, event_name, metadata, created_at }]
@router.get("/api/admin/events")
def list_events(db: Session = Depends(get_db), user: User = Depends(LeadViewer)) -> list[dict]:
    events = list_recent_events(db)
    return [
        {
            "id": event.id,
            "session_token": event.session_token,
            "lead_id": event.lead_id,
            "event_name": event.event_name,
            "metadata": json.loads(event.metadata_json or "{}"),
            "created_at": event.created_at,
        }
        for event in events
    ]

"""
公开接口 — 客户自测流程（无需鉴权）。

客户流程：
  1. POST /sessions        → 创建匿名会话，拿到 session_token
  2. GET  /questions       → 获取 10 模块 68 题
  3. POST /leads           → 填写企业信息，拿到 submission_id
  4. PUT  /submissions/{}/draft → 答题中随时保存草稿
  5. POST /submissions/{}/submit → 提交全部 68 题，规则评分并创建邮件发送任务
  6. GET  /reports/{token}       → 查看已生成报告（含分数 + 维度数据）
  7. GET  /channels/{code}/qr    → 获取渠道二维码图片
"""

import json
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AiConversationMessage, ChannelSource, CompanyLead, DiagnosisSubmission, Report, ReportStatus, SubmissionStatus
from app.repositories.consult_repo import (
    get_lead_by_session,
    get_report_by_public_token,
    get_submission_by_id,
    latest_submission_for_lead,
)
from app.repositories.qr_code_repo import get_active_channel_by_code
from app.schemas import (
    DraftSaveRequest,
    LeadCreate,
    LeadCreatedResponse,
    LeadResponse,
    MessageResponse,
    ModuleRead,
    SessionCreate,
    SessionResponse,
    SubmitQuestionnaireRequest,
    SubmitResponse,
    TrackEventRequest,
)
from app.service.diagnosis import active_modules_with_questions, persist_answers, score_submission
from app.service.report_queue import enqueue_report_delivery
from app.utils.logging_utils import write_tracking_event
from app.utils.qr_code import generate_qr_png
from app.utils.request import client_ip


router = APIRouter()
settings = get_settings()


def is_mysql_deadlock(exc: OperationalError) -> bool:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    return bool(args and args[0] in {1205, 1213})


def report_ai_messages(db: Session, report_id: int) -> list[dict]:
    messages = (
        db.query(AiConversationMessage)
        .filter(AiConversationMessage.report_id == report_id)
        .order_by(AiConversationMessage.created_at.asc())
        .all()
    )
    return [
        {
            "role": message.role,
            "purpose": message.purpose,
            "content": message.content,
            "model_vendor": message.model_vendor,
            "model_name": message.model_name,
            "created_at": message.created_at,
        }
        for message in messages
    ]


# ══════════════════════════════════════════════════════════════════
# 2.1 创建会话
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/public/sessions
# 功能：客户首次进入页面时创建匿名会话，返回 session_token（32位十六进制）
#       前端存入 localStorage，后续所有操作都带这个 token
# 鉴权：无
# 请求：{ source_code?: string, metadata?: object }
# 返回：{ session_token: string }
@router.post("/api/public/sessions", response_model=SessionResponse)
def create_session(payload: SessionCreate, request: Request, db: Session = Depends(get_db)) -> SessionResponse:
    lead = CompanyLead(source_code=payload.source_code or "default")
    db.add(lead)
    db.flush()
    write_tracking_event(
        db,
        "enter_site",
        session_token=lead.session_token,
        lead_id=lead.id,
        metadata=payload.metadata,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )
    db.commit()
    return SessionResponse(session_token=lead.session_token)


# ══════════════════════════════════════════════════════════════════
# 2.2 记录用户行为事件
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/public/events
# 功能：前端埋点，记录用户操作行为
#       事件名：enter_site / click_start / submit_customer_info /
#               submit_questionnaire / view_report_summary / claim_full_report
# 鉴权：无
# 请求：{ session_token?, lead_id?, event_name, metadata? }
# 返回：{ message: "tracked" }
@router.post("/api/public/events", response_model=MessageResponse)
def track_event(payload: TrackEventRequest, request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    write_tracking_event(
        db,
        payload.event_name,
        session_token=payload.session_token,
        lead_id=payload.lead_id,
        metadata=payload.metadata,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )
    db.commit()
    return MessageResponse(message="tracked")


# ══════════════════════════════════════════════════════════════════
# 2.3 获取题库
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/public/questions
# 功能：获取全部活跃模块及题目（10 模块 68 题）
#       每题包含 option_text（0=完全没有；1=...；2=...；3=...；4=...）
# 鉴权：无
# 请求：无参数
# 返回：ModuleRead[] 数组
@router.get("/api/public/questions", response_model=list[ModuleRead])
def list_public_questions(db: Session = Depends(get_db)):
    modules = active_modules_with_questions(db)
    for module in modules:
        module.questions = sorted([q for q in module.questions if q.is_active], key=lambda item: item.sort_order)
    return modules


# ══════════════════════════════════════════════════════════════════
# 2.4 提交企业信息
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/public/leads
# 功能：客户填写企业信息后提交，创建/更新线索，自动创建答题提交记录
# 校验：privacy_accepted 必须为 true
#       phone 和 wechat 至少填一项
# 鉴权：无
# 请求：{ company_name*, industry*, company_size*, contact_name*, position*,
#          phone?, wechat?, ai_focus?, session_token?, ... }
# 返回：{ lead: {...}, submission_id: int }
#       submission_id 用于后续答题和提交
@router.post("/api/public/leads", response_model=LeadCreatedResponse)
def upsert_lead(payload: LeadCreate, request: Request, db: Session = Depends(get_db)) -> LeadCreatedResponse:
    if not payload.privacy_accepted:
        raise HTTPException(status_code=422, detail="请先确认隐私与联系授权")
    if not payload.phone and not payload.wechat:
        raise HTTPException(status_code=422, detail="手机号或微信至少填写一项")

    lead = None
    if payload.session_token:
        lead = get_lead_by_session(db, payload.session_token)
    if not lead:
        lead = CompanyLead(session_token=payload.session_token or None)
        db.add(lead)
        db.flush()

    for field in [
        "company_name",
        "industry",
        "company_size",
        "annual_revenue",
        "contact_name",
        "position",
        "phone",
        "email",
        "wechat",
        "ai_focus",
        "privacy_accepted",
        "contact_authorized",
        "source_code",
    ]:
        setattr(lead, field, getattr(payload, field))

    submission = latest_submission_for_lead(db, lead.id)
    if not submission:
        submission = DiagnosisSubmission(lead_id=lead.id)
        db.add(submission)
        db.flush()

    write_tracking_event(
        db,
        "submit_customer_info",
        session_token=lead.session_token,
        lead_id=lead.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(lead)
    return LeadCreatedResponse(lead=LeadResponse.model_validate(lead), submission_id=submission.id)


# ══════════════════════════════════════════════════════════════════
# 2.5 保存草稿
# ══════════════════════════════════════════════════════════════════
# 方法：PUT
# 路径：/api/public/submissions/{submission_id}/draft
# 功能：答题过程中随时保存已答题目，支持断点续答
#       同一题的答案再次提交会覆盖
# 鉴权：无
# 请求：{ answers: [{ question_id: int, score: 0-4 }] }
# 返回：{ message: "draft saved" }
@router.put("/api/public/submissions/{submission_id}/draft", response_model=MessageResponse)
def save_draft(submission_id: int, payload: DraftSaveRequest, db: Session = Depends(get_db)) -> MessageResponse:
    persist_answers(db, submission_id, payload.answers)
    db.commit()
    return MessageResponse(message="draft saved")


# ══════════════════════════════════════════════════════════════════
# 2.6 提交问卷 + 评分 + 创建报告发送任务
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/public/submissions/{submission_id}/submit
# 功能：客户提交全部 68 题，系统依次执行：
#         ① 保存答案 → ② 规则引擎评分 → ③ 创建报告邮件发送任务
#       后台 worker 再异步调用 DeepSeek、生成 PDF 并发送邮件；
#       如果 AI 调用失败，worker 自动回退到模板报告。
# 鉴权：无
# 请求：{ answers: [{ question_id, score }...] } — 必须包含全部 68 题
#       score 范围 0-4
# 返回：{
#         score: { total_score, max_score, score_rate, risk_level,
#                  dimensions[10], low_dimensions[3] },
#         report: { id, public_token, status, title, html_content, ... }
#       }
# 错误：404 如果 submission_id 不存在
#       422 如果缺少题目答案
@router.post("/api/public/submissions/{submission_id}/submit", response_model=SubmitResponse)
async def submit_questionnaire(
    submission_id: int,
    payload: SubmitQuestionnaireRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SubmitResponse:
    last_deadlock: OperationalError | None = None
    for attempt in range(3):
        try:
            submission = get_submission_by_id(db, submission_id)
            if not submission:
                raise HTTPException(status_code=404, detail="Submission not found")
            persist_answers(db, submission_id, payload.answers)
            submission.status = SubmissionStatus.submitted.value
            submission.submitted_at = datetime.utcnow()
            score = score_submission(db, submission_id)
            report = submission.report
            if not report:
                report = Report(
                    submission_id=submission_id,
                    title=f"{submission.lead.company_name or '企业'} AI 原生转型诊断报告",
                    html_content="",
                    status=ReportStatus.pending.value,
                )
                db.add(report)
                db.flush()
            else:
                report.status = ReportStatus.pending.value
            enqueue_report_delivery(db, report, str(submission.lead.email))
            write_tracking_event(
                db,
                "submit_questionnaire",
                session_token=submission.lead.session_token,
                lead_id=submission.lead_id,
                metadata={"total_score": score.total_score, "risk_level": score.risk_level},
                user_agent=request.headers.get("user-agent"),
                ip_address=client_ip(request),
            )
            db.commit()
            db.refresh(report)
            break
        except OperationalError as exc:
            db.rollback()
            if not is_mysql_deadlock(exc) or attempt == 2:
                raise
            last_deadlock = exc
            await asyncio.sleep(0.1 * (attempt + 1))
    else:
        raise last_deadlock
    return SubmitResponse(
        score=score,
        report={
            "id": report.id,
            "public_token": report.public_token,
            "status": report.status,
            "title": report.title,
            "html_content": report.html_content,
            "model_vendor": report.model_vendor,
            "model_name": report.model_name,
            "created_at": report.created_at,
            "advisor_messages": report_ai_messages(db, report.id),
        },
    )


# ══════════════════════════════════════════════════════════════════
# 2.7 查看公开报告
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/public/reports/{public_token}
# 功能：通过公开 token 查看诊断报告（客户分享链接时使用）
#       返回 HTML 报告内容 + 评分数据 + 维度详情
# 鉴权：无
# 请求：路径参数 public_token
# 返回：{ id, public_token, status, title, html_content, created_at,
#          score: { total, max_score, score_rate, risk_level },
#          dimensions: [{ module_code, module_name, raw_score, max_score, score_rate, risk_level }],
#          low_dimensions: [...] }
@router.get("/api/public/reports/{public_token}")
def public_report(public_token: str, request: Request, db: Session = Depends(get_db)) -> dict:
    report = get_report_by_public_token(db, public_token)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    write_tracking_event(
        db,
        "view_report_summary",
        session_token=report.submission.lead.session_token,
        lead_id=report.submission.lead_id,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )
    db.commit()
    summary = json.loads(report.summary_json or "{}")
    return {
        "id": report.id,
        "public_token": report.public_token,
        "status": report.status,
        "title": report.title,
        "html_content": report.html_content,
        "created_at": report.created_at,
        "score": summary.get("score"),
        "dimensions": summary.get("dimensions", []),
        "low_dimensions": summary.get("low_dimensions", []),
        "customer_classification": summary.get("customer_classification", {}),
        "advisor_messages": report_ai_messages(db, report.id),
    }


# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 2.8 获取渠道二维码
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/public/channels/{code}/qr
# 功能：获取指定渠道的二维码 PNG 图片
#       二维码内容：{PUBLIC_WEB_BASE_URL}/?source={code}
#       扫码后自动携带渠道来源参数
# 鉴权：无（二维码只编码公开 URL，无安全风险）
# 请求：路径参数 code（渠道编码）
# 返回：PNG 图片（Content-Type: image/png）
@router.get("/api/public/channels/{code}/qr")
def public_channel_qr(code: str, db: Session = Depends(get_db)) -> Response:
    channel = get_active_channel_by_code(db, code)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    url = f"{settings.public_web_base_url}/?source={code}"
    return Response(content=generate_qr_png(url), media_type="image/png")

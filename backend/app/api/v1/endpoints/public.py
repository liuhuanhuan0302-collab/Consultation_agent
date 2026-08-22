"""
公开接口 — 客户自测流程（无需鉴权）。

客户流程：
  1. POST /sessions        → 创建匿名会话，拿到 session_token
  2. GET  /questions       → 获取当前启用模块及题目
  3. POST /leads           → 填写企业信息，拿到 submission_id
  4. PUT  /submissions/{}/draft → 答题中随时保存草稿
  5. POST /submissions/{}/submit → 提交当前全部启用题目，规则评分并创建邮件发送任务
  6. GET  /reports/{token}       → 查看已生成报告（含分数 + 维度数据）
  7. GET  /channels/{code}/qr    → 获取渠道二维码图片
"""

import json
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from slowapi import Limiter
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ChannelSource, CompanyLead, DiagnosisSubmission, Report, ReportDeliveryJob, ReportDeliveryStatus, ReportStatus, SubmissionStatus
from app.repositories.consult_repo import (
    get_lead_by_session,
    get_report_by_public_token,
    get_submission_by_id,
    latest_submission_for_lead,
)
from app.repositories.qr_code_repo import get_active_channel_by_code
from app.repositories.questionnaire_repo import active_modules_with_questions
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
from app.service import submission_service
from app.service.report_queue import process_job_then_next
from app.service.reporting import regenerate_report_content_for_testing
from app.service.report_content import sanitize_report_content
from app.utils.logging_utils import write_tracking_event
from app.utils.qr_code import generate_qr_png
from app.utils.request import client_ip
from app.utils.time_utils import utc_now


router = APIRouter()
settings = get_settings()
limiter = Limiter(key_func=client_ip)


def get_submission_for_session(
    submission_id: int,
    session_token: str = Header(alias="X-Session-Token", min_length=20, max_length=64),
    db: Session = Depends(get_db),
) -> DiagnosisSubmission:
    """确认匿名会话持有指定答卷，避免自增 ID 被枚举后越权修改。"""
    submission = get_submission_by_id(db, submission_id)
    if not submission or submission.lead.session_token != session_token:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


def session_rate_limit_key(request: Request) -> str:
    """提交限流同时绑定来源 IP 与匿名会话，避免单个会话被高频滥用。"""
    return f"{client_ip(request)}:{request.headers.get('X-Session-Token', 'anonymous')}"


def enforce_email_lead_limit(db: Session, email: str, current_lead_id: int | None) -> None:
    """限制同邮箱短时间内创建多个匿名线索，保留当前线索的正常更新。"""
    cutoff = utc_now() - timedelta(hours=1)
    query = db.query(func.count(CompanyLead.id)).filter(
        func.lower(CompanyLead.email) == email.lower(),
        CompanyLead.created_at >= cutoff,
    )
    if current_lead_id is not None:
        query = query.filter(CompanyLead.id != current_lead_id)
    if (query.scalar() or 0) >= settings.max_leads_per_email_per_hour:
        raise HTTPException(status_code=429, detail="该邮箱提交过于频繁，请稍后再试")


# 公开接口的失败提示：与前端展示一致，不携带任何内部错误细节。
PUBLIC_REPORT_FAILURE_HINT = "您的诊断资料已收到，报告正在进一步审核，完成后将发送至您的邮箱。"


def serialize_public_report(report: Report) -> dict:
    """组装公开报告响应 — 三个报告接口共用，字段变更只改这一处。"""
    summary = json.loads(report.summary_json or "{}")
    return {
        "id": report.id,
        "public_token": report.public_token,
        "status": report.status,
        "title": report.title,
        "html_content": sanitize_report_content(report.html_content),
        "created_at": report.created_at,
        "score": summary.get("score"),
        "dimensions": summary.get("dimensions", []),
        "low_dimensions": summary.get("low_dimensions", []),
        "core_findings": summary.get("core_findings", []),
        "customer_classification": summary.get("customer_classification", {}),
    }


def is_local_development_request(request: Request) -> bool:
    """本地提示词测试入口不得在服务器或局域网客户端暴露。"""
    return settings.environment == "development" and bool(request.client and request.client.host in {"127.0.0.1", "::1"})


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
@limiter.limit("20/hour")
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
# 功能：获取全部活跃模块及题目
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
@limiter.limit("10/hour")
def upsert_lead(payload: LeadCreate, request: Request, db: Session = Depends(get_db)) -> LeadCreatedResponse:
    if not payload.privacy_accepted:
        raise HTTPException(status_code=422, detail="请先确认隐私与联系授权")
    if not payload.phone and not payload.wechat:
        raise HTTPException(status_code=422, detail="手机号或微信至少填写一项")
    lead = None
    rotated_for_new_round = False
    if payload.session_token:
        lead = get_lead_by_session(db, payload.session_token)
        if lead:
            latest = latest_submission_for_lead(db, lead.id)
            if latest and latest.status != SubmissionStatus.draft.value:
                # 上一轮诊断已完成：新一轮填写改用全新线索与会话，避免覆盖
                # 上一轮的公司信息（旧报告重新生成时会串用新公司名）。
                lead = None
                rotated_for_new_round = True
    if not lead:
        lead = CompanyLead()
        db.add(lead)
        db.flush()
    if rotated_for_new_round:
        # 新一轮会创建全新线索：旧线索同样计入邮箱频控（不排除任何记录），
        # 防止复用已完成会话无限创建线索、消耗检索/生成/邮件资源。
        if payload.email:
            enforce_email_lead_limit(db, str(payload.email), None)
    elif lead.email != payload.email:
        enforce_email_lead_limit(db, str(payload.email), lead.id)

    for field in [
        "company_name",
        "city",
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
    if not submission or submission.status != SubmissionStatus.draft.value:
        # 最近一次答卷已提交（或不存在）：重新填写时新建一条答卷，
        # 避免把新的答题内容提交到已生成的旧报告上。
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
# 鉴权：匿名会话凭证 X-Session-Token（必须与答卷归属一致）
# 请求：{ answers: [{ question_id: int, score: 0-4 }] }
# 返回：{ message: "draft saved" }
@router.put("/api/public/submissions/{submission_id}/draft", response_model=MessageResponse)
def save_draft(
    payload: DraftSaveRequest,
    submission: DiagnosisSubmission = Depends(get_submission_for_session),
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        submission_service.save_submission_draft(
            db,
            submission.id,
            submission.lead.session_token,
            payload.answers,
        )
    except submission_service.SubmissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    except submission_service.SubmissionConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    return MessageResponse(message="draft saved")


# ══════════════════════════════════════════════════════════════════
# 2.6 提交问卷 + 评分 + 创建报告发送任务
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/public/submissions/{submission_id}/submit
# 功能：客户提交当前全部启用题目，系统依次执行：
#         ① 保存答案 → ② 规则引擎评分 → ③ 创建报告邮件发送任务
#       后台 worker 再异步调用 DeepSeek、生成 PDF 并发送邮件；
#       如果 AI 调用失败，worker 自动回退到模板报告。
# 鉴权：匿名会话凭证 X-Session-Token（必须与答卷归属一致）
# 请求：{ answers: [{ question_id, score }...] } — 必须包含当前全部启用题目
#       score 范围 0-4
# 返回：{
#         score: { total_score, max_score, score_rate, risk_level,
#                  dimensions[], low_dimensions[] },
#         report: { id, public_token, status, title, html_content, ... }
#       }
# 错误：404 如果 submission_id 不存在
#       422 如果缺少题目答案
@router.post("/api/public/submissions/{submission_id}/submit", response_model=SubmitResponse)
@limiter.limit("3/hour", key_func=session_rate_limit_key)
async def submit_questionnaire(
    payload: SubmitQuestionnaireRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    submission: DiagnosisSubmission = Depends(get_submission_for_session),
    db: Session = Depends(get_db),
) -> SubmitResponse:
    try:
        result = await submission_service.submit_questionnaire(
            db,
            submission.id,
            request.headers.get("X-Session-Token", ""),
            payload.answers,
            user_agent=request.headers.get("user-agent"),
            ip_address=client_ip(request),
            max_pending_jobs=settings.max_pending_report_jobs,
        )
    except submission_service.SubmissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    except submission_service.SubmissionConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except submission_service.SubmissionValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    except submission_service.SubmissionQueueCapacityError as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc

    score = result.score
    report = result.report
    background_tasks.add_task(process_job_then_next, result.delivery_job_id)
    return SubmitResponse(
        score=score,
        report={
            "id": report.id,
            "public_token": report.public_token,
            "status": report.status,
            "title": report.title,
            "html_content": sanitize_report_content(report.html_content),
            "model_vendor": report.model_vendor,
            "model_name": report.model_name,
            "created_at": report.created_at,
        },
    )


# ══════════════════════════════════════════════════════════════════
# 2.7 查询本次提交的报告状态
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/public/submissions/{submission_id}/report
# 功能：用户返回页面时恢复已提交报告；报告生成完成时供前端自动跳转
# 安全：提交记录必须属于当前浏览器会话（X-Session-Token 请求头，避免
#       凭证进入 URL 被浏览器历史 / Nginx 与访问日志记录）
@router.get("/api/public/submissions/{submission_id}/report")
def submission_report_status(
    submission: DiagnosisSubmission = Depends(get_submission_for_session),
    db: Session = Depends(get_db),
) -> dict:
    report = submission.report
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    data = serialize_public_report(report)
    # 客户只需要任务状态；具体队列位置仅在后台展示，避免暴露系统负载。
    delivery = (
        db.query(ReportDeliveryJob)
        .filter(ReportDeliveryJob.report_id == report.id)
        .order_by(ReportDeliveryJob.id.desc())
        .first()
    )
    if delivery:
        data["delivery_status"] = delivery.status
        # 公开接口不得返回内部异常原文（SMTP/外部 API/文件路径等），
        # 失败时只给出与前端一致的通用提示；详细原因仅后台可见。
        data["delivery_error"] = (
            PUBLIC_REPORT_FAILURE_HINT if delivery.status == ReportDeliveryStatus.failed.value else None
        )
    else:
        data["delivery_status"] = None
        data["delivery_error"] = None
    data["generation_error"] = (
        PUBLIC_REPORT_FAILURE_HINT if report.status == ReportStatus.failed.value else None
    )
    return data


# ══════════════════════════════════════════════════════════════════
# 2.8 按浏览器会话恢复最近报告
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/public/sessions/report
# 功能：兼容旧版本本地未保存 submission_id 的已提交用户
# 安全：session_token 走 X-Session-Token 请求头，不进入 URL 与访问日志
@router.get("/api/public/sessions/report")
def latest_session_report(
    session_token: str = Header(alias="X-Session-Token", min_length=20, max_length=64),
    db: Session = Depends(get_db),
) -> dict:
    lead = get_lead_by_session(db, session_token)
    submission = latest_submission_for_lead(db, lead.id) if lead else None
    report = submission.report if submission else None
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return serialize_public_report(report)


# ══════════════════════════════════════════════════════════════════
# 2.7 查看公开报告
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/public/reports/{public_token}
# 功能：通过公开 token 查看诊断报告（客户分享链接时使用）
#       返回 HTML 报告内容 + 评分数据 + 维度详情
# 鉴权：无
# 请求：路径参数 public_token
# 返回：serialize_public_report 组装的结构（含 score / dimensions / low_dimensions / customer_classification）
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
    return serialize_public_report(report)


# ══════════════════════════════════════════════════════════════════
# 本地提示词测试：重生成当前报告，不发送邮件
# ══════════════════════════════════════════════════════════════════
@router.post("/api/public/reports/{public_token}/regenerate")
@limiter.limit("6/hour")
async def regenerate_report_for_local_testing(public_token: str, request: Request, db: Session = Depends(get_db)) -> dict:
    if not is_local_development_request(request):
        raise HTTPException(status_code=404, detail="Not found")
    report = get_report_by_public_token(db, public_token)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    await regenerate_report_content_for_testing(db, report)
    return serialize_public_report(report)


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

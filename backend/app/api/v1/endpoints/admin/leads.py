"""线索管理 — 列表 / CSV 导出 / 详情 / 更正诊断邮箱 / Word 档案导出 / 手动企业情报检索。"""

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CompanyLead, User
from app.schemas import ExportBatchResponse, LeadDiagnosticEmailUpdate, LeadResponse, MessageResponse
from app.service import lead_service
from app.service.report_queue import process_next_report_delivery
from app.utils.auth import AdminOnly, LeadExporter, LeadViewer

router = APIRouter()


def lead_word_filename(company_name: str | None) -> str:
    """Compatibility export for existing callers and tests."""
    return lead_service.lead_word_filename(company_name)


# ══════════════════════════════════════════════════════════════════
# 3.5 线索列表
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/leads
# 功能：查看所有客户线索，最多 500 条
#       支持按 行业 / 线索等级 / 来源渠道 / 创建日期范围 / 查看状态 /
#       处理状态 / 导出状态 组合筛选（同时满足），sort=newest|oldest
# 鉴权：admin / operator / sales / consultant
# 查询参数（均可选）：
#       ?industry=制造业&lead_level=high&source_code=wechat_mp
#       &created_from=2026-08-01&created_to=2026-08-31&view_status=viewed
#       &processing_status=manual_review&export_status=unexported&sort=oldest
# 返回：LeadResponse[] 数组（默认按最近处理时间倒序）
@router.get("/api/admin/leads", response_model=list[LeadResponse])
def admin_list_leads(
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    view_status: str | None = None,
    processing_status: str | None = None,
    export_status: str | None = None,
    sort: str = "newest",
    db: Session = Depends(get_db),
    user: User = Depends(LeadViewer),
) -> list[CompanyLead]:
    return lead_service.list_admin_leads(
        db,
        industry=industry,
        lead_level=lead_level,
        source_code=source_code,
        created_from=created_from,
        created_to=created_to,
        view_status=view_status,
        processing_status=processing_status,
        export_status=export_status,
        sort=sort,
    )


# ══════════════════════════════════════════════════════════════════
# 3.6 导出筛选结果 CSV
# ══════════════════════════════════════════════════════════════════
# 方法：GET
# 路径：/api/admin/leads/export
# 功能：按当前筛选条件导出 CSV（最多 10 万条），不标记已导出、不建批次
#       筛选参数与线索列表一致；未传筛选参数时导出全部
# 鉴权：admin / operator / sales
# 返回：CSV 文件下载（Content-Type: text/csv）
#       文件名：leads.csv
@router.get("/api/admin/leads/export")
def export_leads(
    industry: str | None = None,
    lead_level: str | None = None,
    source_code: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    view_status: str | None = None,
    processing_status: str | None = None,
    export_status: str | None = None,
    sort: str = "newest",
    db: Session = Depends(get_db),
    user: User = Depends(LeadExporter),
) -> StreamingResponse:
    content = lead_service.export_leads_csv(
        db,
        user,
        industry=industry,
        lead_level=lead_level,
        source_code=source_code,
        created_from=created_from,
        created_to=created_to,
        view_status=view_status,
        processing_status=processing_status,
        export_status=export_status,
        sort=sort,
    )
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


# ══════════════════════════════════════════════════════════════════
# 3.6.0 一键导出未导出客户 + 导出批次历史
# ══════════════════════════════════════════════════════════════════
# POST /api/admin/leads/export-unexported
# 功能：导出全部未导出客户（含尚未查看、AI 失败、待人工处理等），本批标记
#       已导出（首次/最近导出时间），保存 CSV 快照批次与客户清单，支持
#       按历史批次重新下载；同事务行锁防止多人同时导出重复标记
# 鉴权：admin / operator / sales
# 返回：{ batch_id, rows_count, message }，前端随后下载批次文件
@router.post("/api/admin/leads/export-unexported")
def export_unexported_leads(db: Session = Depends(get_db), user: User = Depends(LeadExporter)) -> dict:
    result = lead_service.export_unexported_leads(db, user)
    return {"batch_id": result.batch_id, "rows_count": result.rows_count, "message": result.message}


# GET /api/admin/leads/export-batches
# 功能：导出批次历史（最近 100 批），供管理员重新下载
# 鉴权：admin / operator / sales
@router.get("/api/admin/leads/export-batches", response_model=list[ExportBatchResponse])
def list_export_batches(db: Session = Depends(get_db), user: User = Depends(LeadExporter)) -> list[ExportBatchResponse]:
    return lead_service.list_export_batches(db)


# GET /api/admin/leads/export-batches/{batch_id}/download
# 功能：按历史批次重新下载 CSV 快照
# 鉴权：admin / operator / sales
@router.get("/api/admin/leads/export-batches/{batch_id}/download")
def download_export_batch(
    batch_id: int, db: Session = Depends(get_db), user: User = Depends(LeadExporter)
) -> StreamingResponse:
    try:
        result = lead_service.download_export_batch(db, batch_id)
    except lead_service.LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    return StreamingResponse(
        iter([result.content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="export-batch.csv"; '
                f"filename*=UTF-8''{quote(result.filename)}"
            )
        },
    )


# ══════════════════════════════════════════════════════════════════
# 3.6.1 更正诊断邮箱并重新发送报告
# ══════════════════════════════════════════════════════════════════
@router.put("/api/admin/leads/{lead_id}/diagnostic-email", response_model=MessageResponse)
async def update_lead_diagnostic_email(
    lead_id: int,
    payload: LeadDiagnosticEmailUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> MessageResponse:
    try:
        result = lead_service.update_diagnostic_email(db, user, lead_id, str(payload.email))
    except lead_service.LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    if result.should_process_queue:
        background_tasks.add_task(process_next_report_delivery)
    return MessageResponse(message=result.message)


# ══════════════════════════════════════════════════════════════════
# 3.6.2 导出单个客户 Word 档案
# ══════════════════════════════════════════════════════════════════
@router.get("/api/admin/leads/{lead_id}/export/word")
def export_lead_word(lead_id: int, db: Session = Depends(get_db), user: User = Depends(LeadExporter)) -> StreamingResponse:
    try:
        result = lead_service.export_lead_word(db, user, lead_id)
    except lead_service.LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    return StreamingResponse(
        iter([result.document]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                'attachment; filename="customer-detail.docx"; '
                f"filename*=UTF-8''{quote(result.filename)}"
            )
        },
    )


# ══════════════════════════════════════════════════════════════════
# 3.6.3 查看线索详情
# ══════════════════════════════════════════════════════════════════
# 首次打开详情时记录查看状态（已经查看 + 首次查看时间/人），之后重复
# 打开与轮询刷新不再重复记录；查看不改变导出状态。
@router.get("/api/admin/leads/{lead_id}")
def admin_get_lead_detail(
    lead_id: int, db: Session = Depends(get_db), user: User = Depends(LeadViewer)
) -> dict:
    try:
        return lead_service.get_lead_detail(db, lead_id, user)
    except lead_service.LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc


# ══════════════════════════════════════════════════════════════════
# 3.6.5 删除线索（级联清理）
# ══════════════════════════════════════════════════════════════════
# 方法：DELETE
# 路径：/api/admin/leads/{lead_id}
# 功能：删除一条客户线索及其全部关联数据（企业信息、答题、评分、报告、
#       AI 会话消息、报告投递任务、埋点事件）。删除后该客户可重新填写。
# 鉴权：仅 admin
@router.delete("/api/admin/leads/{lead_id}", response_model=MessageResponse)
def admin_delete_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> MessageResponse:
    try:
        message = lead_service.delete_lead(db, user, lead_id)
    except lead_service.LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    return MessageResponse(message=message)


# ══════════════════════════════════════════════════════════════════
# 3.6.4 手动检索企业情报与 AI 分析
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/leads/{lead_id}/research
# 功能：手动触发联网搜索 + AI 提炼（7 类企业情报与综合分析），force=true 时重新生成
#       检索在后台任务中异步执行，接口立即返回；前端轮询线索详情刷新结果
# 鉴权：仅 admin
# 返回：{ status: "started" | "already_generated", message }
@router.post("/api/admin/leads/{lead_id}/research")
def trigger_lead_research(
    lead_id: int,
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> dict:
    try:
        result = lead_service.trigger_research(db, user, lead_id, force)
    except (lead_service.LeadNotFoundError, lead_service.LeadReportNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    except lead_service.LeadValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    if result.report_id is not None:
        background_tasks.add_task(lead_service.run_company_research_task, result.report_id, result.force)
    return {"status": result.status, "message": result.message}


# ══════════════════════════════════════════════════════════════════
# 3.6.6 继续生成报告并发送
# ══════════════════════════════════════════════════════════════════
# 方法：POST
# 路径：/api/admin/leads/{lead_id}/resume-delivery
# 功能：企业情报已生成、但报告/投递任务失败（含重试耗尽）时，重置报告与
#       投递任务状态重新入队，从已有企业情报继续：生成 AI 报告 → PDF → 邮件，
#       不重新搜索。队列在后台任务中唤醒，接口立即返回。
# 鉴权：仅 admin
# 返回：{ message }
@router.post("/api/admin/leads/{lead_id}/resume-delivery", response_model=MessageResponse)
async def resume_lead_report_delivery(
    lead_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> MessageResponse:
    try:
        result = lead_service.resume_report_delivery(db, user, lead_id)
    except (lead_service.LeadNotFoundError, lead_service.LeadReportNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc
    except lead_service.LeadValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    if result.should_process_queue:
        background_tasks.add_task(process_next_report_delivery)
    return MessageResponse(message=result.message)

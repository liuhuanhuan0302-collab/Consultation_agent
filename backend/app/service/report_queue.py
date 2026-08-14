import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Report, ReportDeliveryJob, ReportDeliveryStatus, ReportStatus
from app.service.company_research import research_company
from app.service.email_service import send_report_pdf_email
from app.service.pdf_service import render_report_html_attachment, render_report_pdf_bytes, report_public_url
from app.service.reporting import generate_report_content, report_generation_semaphore
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

# 单个报告通常会在数分钟内完成。超过该时长仍处于处理中，说明 worker
# 大概率在生成报告或发送邮件的过程中退出，需要重新放回队列。
STALE_PROCESSING_TIMEOUT = timedelta(minutes=15)


def enqueue_report_delivery(db: Session, report: Report, recipient_email: str) -> ReportDeliveryJob:
    """创建或复用报告发送任务，提交接口只负责入队，不等待 AI 和邮件。"""
    normalized_email = (recipient_email or "").strip().lower()
    if not normalized_email:
        raise ValueError("报告接收邮箱为空，无法加入发送队列")

    existing = (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.report_id == report.id,
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
        )
        .first()
    )
    if existing:
        existing.recipient_email = normalized_email
        existing.run_after = utc_now()
        return existing

    # processing 中的任务已不在候选之列：worker 读取收件人发生在领取之后，
    # 直接改它的 recipient_email 可能不生效，因此为更正后的邮箱新建一条任务补发。

    job = ReportDeliveryJob(
        lead_id=report.submission.lead_id,
        submission_id=report.submission_id,
        report_id=report.id,
        recipient_email=normalized_email,
        status=ReportDeliveryStatus.queued.value,
        run_after=utc_now(),
    )
    db.add(job)
    db.flush()
    return job


def claim_next_job(db: Session) -> ReportDeliveryJob | None:
    """领取一条待处理任务，并先回收意外中断的处理任务。

    领取通过条件 UPDATE（WHERE status=queued）原子完成：多个 worker
    并发调用时只有一个能拿到 rowcount=1，避免同一任务被重复生成报告、
    重复发送邮件。
    """
    now = utc_now()
    stale_before = now - STALE_PROCESSING_TIMEOUT

    stale_jobs = (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
            ReportDeliveryJob.locked_at.is_not(None),
            ReportDeliveryJob.locked_at < stale_before,
        )
        .all()
    )
    for stale_job in stale_jobs:
        if stale_job.attempts >= stale_job.max_attempts:
            stale_job.status = ReportDeliveryStatus.failed.value
            stale_job.last_error = "任务处理超时，已达到最大重试次数"
        else:
            stale_job.status = ReportDeliveryStatus.queued.value
            stale_job.run_after = now
            stale_job.last_error = "任务处理超时，已重新加入队列"
        stale_job.locked_at = None

    if stale_jobs:
        logger.warning("回收了 %s 条超时的报告发送任务", len(stale_jobs))
        db.commit()

    while True:
        candidate_id = (
            db.query(ReportDeliveryJob.id)
            .filter(
                ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
                ReportDeliveryJob.run_after <= now,
                ReportDeliveryJob.attempts < ReportDeliveryJob.max_attempts,
            )
            .order_by(ReportDeliveryJob.created_at.asc())
            .limit(1)
            .scalar()
        )
        if not candidate_id:
            return None
        if _try_claim_job(db, candidate_id, now):
            return db.get(ReportDeliveryJob, candidate_id)


def _try_claim_job(db: Session, job_id: int, now: datetime) -> bool:
    """条件 UPDATE 原子认领：只有状态仍为 queued 时才生效，防止并发重复领取。"""
    result = db.execute(
        update(ReportDeliveryJob)
        .where(
            ReportDeliveryJob.id == job_id,
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
        )
        .values(
            status=ReportDeliveryStatus.processing.value,
            locked_at=now,
            attempts=ReportDeliveryJob.attempts + 1,
        )
    )
    db.commit()
    return result.rowcount == 1


async def process_report_delivery_job(job_id: int) -> bool:
    """生成报告、渲染 PDF 并发送邮件。返回 True 表示任务完成。"""
    db = SessionLocal()
    try:
        job = db.query(ReportDeliveryJob).filter(ReportDeliveryJob.id == job_id).first()
        if not job:
            return True
        report = db.query(Report).filter(Report.id == job.report_id).first()
        if not report:
            job.status = ReportDeliveryStatus.failed.value
            job.last_error = "报告不存在"
            db.commit()
            return True

        if not (report.status in {ReportStatus.generated.value, ReportStatus.fallback.value} and report.html_content):
            report.status = ReportStatus.generating.value
            db.commit()
            db.refresh(report)
            await research_company(db, report)  # 联网情报检索，失败静默降级
            async with report_generation_semaphore():
                await generate_report_content(db, report)
        pdf = await render_report_pdf_bytes(report)
        html = render_report_html_attachment(report)
        report_url = report_public_url(report)
        send_report_pdf_email(
            job.recipient_email,
            report.title,
            pdf,
            f"diagnosis-report-{report.public_token}.pdf",
            report_url=report_url,
            html_bytes=html,
            html_filename=f"diagnosis-report-{report.public_token}.html",
        )

        job.status = ReportDeliveryStatus.sent.value
        job.sent_at = utc_now()
        job.locked_at = None
        job.last_error = None
        db.commit()
        return True
    except Exception as exc:
        logger.exception("报告发送任务失败: job_id=%s", job_id)
        db.rollback()
        job = db.query(ReportDeliveryJob).filter(ReportDeliveryJob.id == job_id).first()
        if job:
            job.last_error = str(exc)
            if job.attempts >= job.max_attempts:
                job.status = ReportDeliveryStatus.failed.value
            else:
                job.status = ReportDeliveryStatus.queued.value
                job.run_after = utc_now() + timedelta(minutes=2 * job.attempts)
            job.locked_at = None
            db.commit()
        return False
    finally:
        db.close()


async def process_next_report_delivery() -> bool:
    """领取并处理一条报告任务，供 Web 请求结束后的后台任务调用。"""
    db = SessionLocal()
    try:
        job = claim_next_job(db)
    finally:
        db.close()
    if not job:
        return False
    return await process_report_delivery_job(job.id)


async def run_report_delivery_worker(poll_interval_seconds: float = 2.0) -> None:
    """持续消费报告发送队列。部署时作为单独进程启动。"""
    while True:
        db = SessionLocal()
        try:
            job = claim_next_job(db)
        finally:
            db.close()
        if not job:
            await asyncio.sleep(poll_interval_seconds)
            continue
        await process_report_delivery_job(job.id)

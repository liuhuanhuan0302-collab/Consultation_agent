import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Report, ReportDeliveryJob, ReportDeliveryStatus, ReportStatus
from app.service.email_service import send_report_pdf_email
from app.service.pdf_service import render_report_pdf_bytes
from app.service.reporting import generate_report_content

logger = logging.getLogger(__name__)


def enqueue_report_delivery(db: Session, report: Report, recipient_email: str) -> ReportDeliveryJob:
    """创建或复用报告发送任务，提交接口只负责入队，不等待 AI 和邮件。"""
    existing = (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.report_id == report.id,
            ReportDeliveryJob.status.in_([ReportDeliveryStatus.queued.value, ReportDeliveryStatus.processing.value]),
        )
        .first()
    )
    if existing:
        existing.recipient_email = recipient_email
        existing.run_after = datetime.utcnow()
        return existing

    job = ReportDeliveryJob(
        lead_id=report.submission.lead_id,
        submission_id=report.submission_id,
        report_id=report.id,
        recipient_email=recipient_email,
        status=ReportDeliveryStatus.queued.value,
        run_after=datetime.utcnow(),
    )
    db.add(job)
    db.flush()
    return job


def claim_next_job(db: Session) -> ReportDeliveryJob | None:
    """领取一条待处理任务。单 worker 足够首版使用，多 worker 后续可加行级锁。"""
    job = (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
            ReportDeliveryJob.run_after <= datetime.utcnow(),
            ReportDeliveryJob.attempts < ReportDeliveryJob.max_attempts,
        )
        .order_by(ReportDeliveryJob.created_at.asc())
        .first()
    )
    if not job:
        return None
    job.status = ReportDeliveryStatus.processing.value
    job.locked_at = datetime.utcnow()
    job.attempts += 1
    db.commit()
    db.refresh(job)
    return job


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

        report.status = ReportStatus.generating.value
        db.commit()
        db.refresh(report)

        await generate_report_content(db, report)
        pdf = render_report_pdf_bytes(report)
        send_report_pdf_email(
            job.recipient_email,
            report.title,
            pdf,
            f"diagnosis-report-{report.public_token}.pdf",
        )

        job.status = ReportDeliveryStatus.sent.value
        job.sent_at = datetime.utcnow()
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
                job.run_after = datetime.utcnow() + timedelta(minutes=2 * job.attempts)
            db.commit()
        return False
    finally:
        db.close()


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

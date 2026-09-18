import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import case, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    CompanyResearchStatus,
    Report,
    ReportDeliveryJob,
    ReportDeliveryStatus,
    ReportFileStatus,
    ReportQueueState,
    ReportStatus,
    ReportTaskKind,
)
from app.service.company_research import research_company
from app.service.email_service import send_report_pdf_email
from app.service.lead_status import sync_lead_processing_status
from app.service.pdf_service import (
    CustomerPdfConversionError,
    customer_report_filename,
    render_report_pdf_bytes,
    report_public_url,
)
from app.service.reporting import generate_report_content, report_generation_semaphore
from app.service.report_queue_scheduler import (
    acquire_pdf_slot,
    claim_next_job_locked,
    finish_job,
    place_delivery_job_in_transaction,
    promote_waiting_jobs,
)
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

# 租约心跳间隔：执行中的任务每 30 秒续约一次 locked_at。远小于回收阈值，
# 存活的任务永远不会被误回收；进程死亡后心跳停止，任务才会在阈值后被重新入队。
HEARTBEAT_INTERVAL_SECONDS = 30.0

# 回收阈值必须大于流水线最大耗时，否则执行中的任务会被重新入队，导致重复
# 生成、重复邮件。最坏情况估算：单次 LLM 超时 ×（检索 2 次 + 报告生成
# 1 + 3 次纠错 + 2 次 pause 续接 ≈ 8 次调用）+ 搜索 / PDF / SMTP 开销。
# 按超时秒数 × 10 计算并保底 15 分钟，随 DEEPSEEK_TIMEOUT_SECONDS 自适应。
STALE_PROCESSING_TIMEOUT = timedelta(
    minutes=max(15.0, get_settings().deepseek_timeout_seconds * 10 / 60)
)


def enqueue_report_delivery(
    db: Session,
    report: Report,
    recipient_email: str,
    *,
    task_kind: ReportTaskKind | str = ReportTaskKind.full_delivery,
    task_context: dict | None = None,
) -> ReportDeliveryJob:
    """创建或复用报告发送任务，提交接口只负责入队，不等待 AI 和邮件。"""
    normalized_email = (recipient_email or "").strip().lower()
    kind = task_kind.value if isinstance(task_kind, ReportTaskKind) else str(task_kind)
    delivery_kinds = {
        ReportTaskKind.full_delivery.value,
        ReportTaskKind.attachment_delivery.value,
    }
    if kind in delivery_kinds and not normalized_email:
        raise ValueError("报告接收邮箱为空，无法加入发送队列")

    existing = (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.report_id == report.id,
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
            ReportDeliveryJob.task_kind == kind,
        )
        .first()
    )
    if existing:
        existing.recipient_email = normalized_email
        existing.run_after = utc_now()
        existing.task_context_json = json.dumps(task_context, ensure_ascii=False) if task_context else None
        return existing

    # processing 中的任务已不在候选之列：worker 读取收件人发生在领取之后，
    # 直接改它的 recipient_email 可能不生效，因此为更正后的邮箱新建一条任务补发。

    job = ReportDeliveryJob(
        lead_id=report.submission.lead_id,
        submission_id=report.submission_id,
        report_id=report.id,
        recipient_email=normalized_email,
        status=ReportDeliveryStatus.queued.value,
        task_kind=kind,
        task_context_json=json.dumps(task_context, ensure_ascii=False) if task_context else None,
        run_after=utc_now(),
    )
    db.add(job)
    db.flush()
    place_delivery_job_in_transaction(db, job.id)
    return job


def claim_next_job(db: Session) -> ReportDeliveryJob | None:
    """领取一条待处理任务，并先回收超时未续约的处理任务。

    领取通过条件 UPDATE（WHERE status=queued）原子完成：多个 worker
    并发调用时只有一个能拿到 rowcount=1，避免同一任务被重复生成报告、
    重复发送邮件。
    """
    _reclaim_stale_jobs(db)
    promote_waiting_jobs(db)
    return claim_next_job_locked(db, at=utc_now())


def _reclaim_stale_jobs(db: Session) -> int:
    """原子回收超过阈值未续约的处理中任务（进程死亡遗留）。

    条件 UPDATE 同时充当并发互斥：多个 worker 并发回收时，只有第一个能
    改掉状态（第二个执行的 status='processing' 条件不再成立）。回收时
    清空 lock_token，使旧执行者后续的任何条件写入失效，杜绝重复邮件。
    """
    now = utc_now()
    stale_before = now - STALE_PROCESSING_TIMEOUT
    stale_rows = (
        db.query(ReportDeliveryJob.id, ReportDeliveryJob.lead_id)
        .filter(
            ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
            ReportDeliveryJob.locked_at.is_not(None),
            ReportDeliveryJob.locked_at < stale_before,
        )
        .all()
    )
    if not stale_rows:
        return 0

    exhausted = ReportDeliveryJob.attempts >= ReportDeliveryJob.max_attempts
    result = db.execute(
        update(ReportDeliveryJob)
        .where(
            ReportDeliveryJob.id.in_([row.id for row in stale_rows]),
            ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
            ReportDeliveryJob.locked_at.is_not(None),
            ReportDeliveryJob.locked_at < stale_before,
        )
        .values(
            status=case(
                (exhausted, ReportDeliveryStatus.failed.value),
                else_=ReportDeliveryStatus.queued.value,
            ),
            last_error=case(
                (exhausted, "任务处理超时，已达到最大重试次数"),
                else_="任务处理超时，已重新加入队列",
            ),
            run_after=now,
            locked_at=None,
            lock_token=None,
            processing_stage=None,
            queue_state=case(
                (exhausted, ReportQueueState.manual_review.value),
                else_=ReportQueueState.active.value,
            ),
        )
    )
    db.commit()
    for row in stale_rows:
        sync_lead_processing_status(db, row.lead_id)
    if result.rowcount:
        db.commit()
    logger.warning("回收了 %s 条超时的报告发送任务", result.rowcount)
    return result.rowcount


def _try_claim_job(db: Session, job_id: int, now: datetime) -> bool:
    """条件 UPDATE 原子认领：仅当任务仍为 queued、已到重试时间且未超最大
    次数时才生效。条件与 claim_next_job 的候选筛选一致，既防止并发重复
    领取，也防止定向领取（提交接口的后台任务）绕过失败后的退避时间。

    认领同时签发一次性租约 token（lock_token）：执行期间的所有状态写入
    都必须携带该 token，超时回收后旧执行者无法覆盖新执行者的结果。
    """
    result = db.execute(
        update(ReportDeliveryJob)
        .where(
            ReportDeliveryJob.id == job_id,
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
            ReportDeliveryJob.run_after <= now,
            ReportDeliveryJob.attempts < ReportDeliveryJob.max_attempts,
        )
        .values(
            status=ReportDeliveryStatus.processing.value,
            locked_at=now,
            lock_token=uuid.uuid4().hex,
            attempts=ReportDeliveryJob.attempts + 1,
        )
    )
    db.commit()
    return result.rowcount == 1


def _adopt_lease(db: Session, job_id: int) -> str | None:
    """旧版本认领或直接调用的任务没有租约 token：签发一个并转 processing。

    条件 UPDATE 失败（任务已被回收或已归属其他执行者）返回 None。
    """
    token = uuid.uuid4().hex
    now = utc_now()
    rowcount = db.execute(
        update(ReportDeliveryJob)
        .where(
            ReportDeliveryJob.id == job_id,
            ReportDeliveryJob.status.in_(
                [ReportDeliveryStatus.queued.value, ReportDeliveryStatus.processing.value]
            ),
            ReportDeliveryJob.lock_token.is_(None),
        )
        .values(
            status=ReportDeliveryStatus.processing.value,
            locked_at=now,
            lock_token=token,
        )
    ).rowcount
    db.commit()
    return token if rowcount == 1 else None


def _touch_lease(db: Session, job_id: int, lock_token: str) -> int:
    """租约续约条件更新：仅当任务仍处理中且 token 匹配时刷新 locked_at。

    返回影响行数：1 表示租约有效；0 表示任务已被回收或重新认领。
    """
    rowcount = db.execute(
        update(ReportDeliveryJob)
        .where(
            ReportDeliveryJob.id == job_id,
            ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
            ReportDeliveryJob.lock_token == lock_token,
        )
        .values(locked_at=utc_now())
    ).rowcount
    db.commit()
    return rowcount


def _set_processing_stage(db: Session, job_id: int, lock_token: str, stage: str) -> bool:
    rowcount = db.execute(
        update(ReportDeliveryJob)
        .where(
            ReportDeliveryJob.id == job_id,
            ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
            ReportDeliveryJob.lock_token == lock_token,
        )
        .values(processing_stage=stage)
    ).rowcount
    db.commit()
    return rowcount == 1


async def _heartbeat_loop(job_id: int, lock_token: str, stop_event: asyncio.Event) -> None:
    """租约续约循环：任务执行期间定时刷新 locked_at。

    续约是条件 UPDATE（WHERE lock_token=本任务 token）：一旦任务被回收
    （状态不再是 processing 或 token 被清空），影响行数为 0，立即置
    stop_event。主流程在每个检查点看到该事件后放弃执行，不再生成或发邮件。
    """
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_INTERVAL_SECONDS)
            return
        except TimeoutError:
            pass
        db = SessionLocal()
        try:
            if _touch_lease(db, job_id, lock_token) != 1:
                stop_event.set()
                return
        except Exception:
            db.rollback()
            logger.warning("租约续约失败（暂不中断任务）: job_id=%s", job_id, exc_info=True)
        finally:
            db.close()


async def process_report_delivery_job(job_id: int) -> bool:
    """执行报告任务；PDF 导出任务只渲染并持久化，不发送邮件。"""
    db = SessionLocal()
    stage = "initializing"
    heartbeat_task: asyncio.Task | None = None
    stop_event = asyncio.Event()
    lock_token: str | None = None
    try:
        job = db.query(ReportDeliveryJob).filter(ReportDeliveryJob.id == job_id).first()
        if not job:
            return True
        lock_token = job.lock_token or _adopt_lease(db, job_id)
        if lock_token is None:
            logger.warning("任务已被回收或重新认领，放弃执行: job_id=%s", job_id)
            return False
        heartbeat_task = asyncio.create_task(_heartbeat_loop(job_id, lock_token, stop_event))

        report = db.query(Report).filter(Report.id == job.report_id).first()
        if not report:
            completed = finish_job(
                db,
                job_id,
                lock_token,
                status=ReportDeliveryStatus.failed.value,
                error="报告不存在",
            )
            return True

        task_kind = str(job.task_kind or ReportTaskKind.full_delivery.value)
        context = json.loads(job.task_context_json) if job.task_context_json else {}

        if task_kind == ReportTaskKind.research_only.value:
            stage = "research"
            if not _set_processing_stage(db, job_id, lock_token, stage):
                return False
            report.research_status = CompanyResearchStatus.processing.value
            report.research_started_at = utc_now()
            db.commit()
            result = await research_company(db, report, force=bool(context.get("force")))
            if not result:
                raise RuntimeError(report.generation_error or "公司情报检索失败")
            finish_job(
                db,
                job_id,
                lock_token,
                status=ReportDeliveryStatus.cancelled.value,
            )
            sync_lead_processing_status(db, job.lead_id)
            db.commit()
            return True

        if task_kind == ReportTaskKind.content_regeneration.value:
            stage = "report"
            if not _set_processing_stage(db, job_id, lock_token, stage):
                return False
            db.commit()
            from app.service.lead_service import run_report_regeneration_task

            started = context.get("generation_started_at")
            generation_started_at = datetime.fromisoformat(started) if started else None
            if generation_started_at is None:
                raise RuntimeError("内容重生成任务缺少租约时间")
            if not (
                report.status == ReportStatus.generating.value
                and report.generation_started_at == generation_started_at
            ):
                report.status = ReportStatus.generating.value
                report.generation_started_at = generation_started_at
                report.generation_completed_at = None
                report.generation_error = None
                db.commit()
            await run_report_regeneration_task(
                report.id,
                context.get("user_id"),
                context.get("previous_status", ReportStatus.generated.value),
                generation_started_at,
                queue_job_id=job_id,
                queue_lock_token=lock_token,
            )
            db.expire_all()
            current_report = db.get(Report, report.id)
            error = current_report.generation_error if current_report else "报告不存在"
            if current_report is None or error:
                raise RuntimeError(error or "AI 报告重新生成失败")
            completed = finish_job(
                db,
                job_id,
                lock_token,
                status=ReportDeliveryStatus.cancelled.value,
                error=None,
            )
            if completed:
                sync_lead_processing_status(db, job.lead_id)
                db.commit()
            return current_report is not None and current_report.status in (
                ReportStatus.generated.value,
                ReportStatus.fallback.value,
            )

        if stop_event.is_set():
            return False

        reusable_report_statuses = (
            ReportStatus.generated.value,
            ReportStatus.fallback.value,
        )
        reuse_only_task_kinds = {
            ReportTaskKind.attachment_delivery.value,
            ReportTaskKind.pdf_export.value,
        }
        if task_kind in reuse_only_task_kinds and not (
            report.status in reusable_report_statuses and report.html_content
        ):
            raise RuntimeError("当前没有可导出的完整 AI 报告")
        if task_kind not in reuse_only_task_kinds and not (
            report.status in reusable_report_statuses and report.html_content
        ):
            stage = "research"
            if not _set_processing_stage(db, job_id, lock_token, stage):
                return False
            report.status = ReportStatus.pending.value
            report.research_status = CompanyResearchStatus.processing.value
            report.research_started_at = utc_now()
            db.commit()
            db.refresh(report)
            sync_lead_processing_status(db, job.lead_id)
            db.commit()
            research = await research_company(db, report)
            if stop_event.is_set():
                return False
            if not research:
                error = report.generation_error or "公司情报检索暂时失败"
                if job.attempts < job.max_attempts:
                    delay_minutes = max(2, 2 * job.attempts)
                    report.status = ReportStatus.pending.value
                    report.research_status = CompanyResearchStatus.pending.value
                    next_status = ReportDeliveryStatus.queued.value
                    run_after = utc_now() + timedelta(minutes=delay_minutes)
                    next_error = f"{error}；将在 {delay_minutes} 分钟后自动重试"
                else:
                    report.status = ReportStatus.failed.value
                    report.research_status = CompanyResearchStatus.review.value
                    report.generation_error = f"{error}；自动重试已耗尽，待人工审核"
                    next_status = ReportDeliveryStatus.failed.value
                    run_after = None
                    next_error = report.generation_error
                db.commit()
                if finish_job(
                    db,
                    job_id,
                    lock_token,
                    status=next_status,
                    error=next_error,
                    run_after=run_after,
                ):
                    sync_lead_processing_status(db, job.lead_id)
                    db.commit()
                return False
            report.status = ReportStatus.generating.value
            report.generation_started_at = utc_now()
            db.commit()
            async with report_generation_semaphore():
                stage = "report"
                if not _set_processing_stage(db, job_id, lock_token, stage):
                    return False
                await generate_report_content(db, report)
            # 报告生成与邮件投递是两个独立结果。先固化报告，避免 SMTP/PDF
            # 失败时异常回滚掉已生成内容，导致客户永久停留在“生成中”。
            db.commit()
            db.refresh(report)
            if report.status != ReportStatus.generated.value or not report.html_content:
                # 报告生成失败与检索失败一样按 attempts 退避重试：短时模型
                # 故障自动恢复，而不是直接转人工处理。情报已缓存，重试会
                # 复用证据直接重新生成。
                error = report.generation_error or "报告内容不完整，待人工审核"
                if job.attempts < job.max_attempts:
                    delay_minutes = max(2, 2 * job.attempts)
                    report.status = ReportStatus.pending.value
                    next_status = ReportDeliveryStatus.queued.value
                    run_after = utc_now() + timedelta(minutes=delay_minutes)
                    next_error = f"{error}；将在 {delay_minutes} 分钟后自动重试"
                else:
                    report.status = ReportStatus.failed.value
                    next_status = ReportDeliveryStatus.failed.value
                    run_after = None
                    next_error = f"{error}；自动重试已耗尽，待人工审核"
                db.commit()
                if finish_job(
                    db,
                    job_id,
                    lock_token,
                    status=next_status,
                    error=next_error,
                    run_after=run_after,
                ):
                    sync_lead_processing_status(db, job.lead_id)
                    db.commit()
                return False
        stage = "waiting_pdf"
        if not _set_processing_stage(db, job_id, lock_token, stage):
            return False
        while not acquire_pdf_slot(db, job_id, lock_token):
            if stop_event.is_set():
                return False
            await asyncio.sleep(0.25)
        stage = "pdf"
        report.pdf_status = ReportFileStatus.processing.value
        report.pdf_started_at = utc_now()
        report.pdf_completed_at = None
        db.commit()
        pdf = await render_report_pdf_bytes(report)
        report.pdf_status = ReportFileStatus.generated.value
        report.pdf_completed_at = utc_now()
        db.commit()
        if stop_event.is_set():
            return False
        if task_kind == ReportTaskKind.pdf_export.value:
            stage = "persisting_pdf"
            if not _set_processing_stage(db, job_id, lock_token, stage):
                return False
            # finish_job verifies and locks the queue lease before committing.
            # Keeping this assignment uncommitted makes artifact publication
            # and the terminal transition one lease-fenced transaction.
            report.customer_pdf_bytes = pdf
            completed = finish_job(
                db,
                job_id,
                lock_token,
                status=ReportDeliveryStatus.cancelled.value,
            )
            return bool(completed)
        report_url = report_public_url(report)
        stage = "email"
        if not _set_processing_stage(db, job_id, lock_token, stage):
            return False
        # 发邮件前最后确认租约仍归本执行者所有：心跳停止期间被回收的任务
        # 不得再发送邮件，防止同一任务被重复投递。
        db.expire_all()
        job = db.get(ReportDeliveryJob, job_id)
        if not job or job.status != ReportDeliveryStatus.processing.value or job.lock_token != lock_token:
            logger.warning("租约已失效，放弃发送邮件: job_id=%s", job_id)
            return False
        send_report_pdf_email(
            job.recipient_email,
            report.title,
            pdf,
            customer_report_filename(report),
            report_url=report_url,
        )

        # 终态写入同样是条件更新：租约已丢失时不覆盖新执行者的结果。
        # customer_pdf_bytes 与邮件调用接收的是同一个局部 pdf 对象，确保
        # 管理员后来下载的客户版 PDF 与实际发送的附件逐字节一致。
        report.customer_pdf_bytes = pdf
        updated = db.execute(
            update(ReportDeliveryJob)
            .where(
                ReportDeliveryJob.id == job_id,
                ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
                ReportDeliveryJob.lock_token == lock_token,
            )
            .values(
                status=ReportDeliveryStatus.sent.value,
                sent_at=utc_now(),
                locked_at=None,
                lock_token=None,
                last_error=None,
                queue_state=None,
                processing_stage=None,
            )
        ).rowcount
        if updated != 1:
            db.rollback()
            logger.warning("租约已失效，发送结果未写入: job_id=%s", job_id)
            return False
        db.commit()
        promote_waiting_jobs(db)
        sync_lead_processing_status(db, job.lead_id)
        db.commit()
        return True
    except Exception as exc:
        logger.exception("报告发送任务失败: job_id=%s", job_id)
        db.rollback()
        job = (
            db.query(ReportDeliveryJob)
            .filter(
                ReportDeliveryJob.id == job_id,
                ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
                ReportDeliveryJob.lock_token == lock_token,
            )
            .first()
            if lock_token
            else None
        )
        if job:
            lead_id = job.lead_id
            report = db.query(Report).filter(Report.id == job.report_id).first()
            if report and stage == "pdf":
                report.pdf_status = ReportFileStatus.failed.value
                report.pdf_completed_at = utc_now()
            stage_labels = {
                "research": "企业情报检索失败",
                "report": "AI 报告生成失败",
                "pdf": "PDF 生成或校验失败",
                "email": "邮件发送失败",
            }
            next_error = f"{stage_labels.get(stage, '报告任务失败')}：{exc}"
            terminal_attachment_failure = (
                task_kind != ReportTaskKind.pdf_export.value
                and stage == "pdf"
                and isinstance(exc, CustomerPdfConversionError)
            )
            if terminal_attachment_failure:
                next_status = ReportDeliveryStatus.failed.value
                run_after = None
                next_error = (
                    "PDF 附件生成失败：Word→PDF 已连续尝试 3 次，未发送邮件，已转人工处理；"
                    "请修复服务器转换环境后点击“重新生成附件并发送”"
                )
            elif job.attempts >= job.max_attempts:
                next_status = ReportDeliveryStatus.failed.value
                run_after = None
            else:
                next_status = ReportDeliveryStatus.queued.value
                run_after = utc_now() + timedelta(minutes=2 * job.attempts)
            db.commit()
            if finish_job(
                db,
                job_id,
                lock_token,
                status=next_status,
                error=next_error,
                run_after=run_after,
            ):
                if task_kind != ReportTaskKind.pdf_export.value:
                    sync_lead_processing_status(db, lead_id)
                    db.commit()
        else:
            logger.warning("租约已失效，失败状态未写入: job_id=%s", job_id)
        return False
    finally:
        stop_event.set()
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        db.close()


async def run_report_delivery_worker(poll_interval_seconds: float = 2.0) -> None:
    """Dynamic independent supervisor; database claims enforce global limits."""
    running: set[asyncio.Task] = set()
    while True:
        finished = {task for task in running if task.done()}
        for task in finished:
            try:
                task.result()
            except Exception:
                logger.exception("报告 worker 子任务异常")
        running -= finished
        db = SessionLocal()
        try:
            job = claim_next_job(db)
        finally:
            db.close()
        if not job:
            await asyncio.sleep(poll_interval_seconds)
            continue
        running.add(asyncio.create_task(process_report_delivery_job(job.id)))

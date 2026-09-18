"""Atomic placement and administration for the persistent report queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from app.models.common import now
from app.models.report import ReportDeliveryJob, ReportDeliveryStatus, ReportQueueState
from app.models.system_setting import ReportQueueSetting
from app.repositories import report_queue_repo
from app.repositories.system_setting_repo import (
    get_report_queue_settings,
    lock_report_queue_settings,
)


class ReportQueueSchedulerError(Exception):
    """Base exception for scheduler-domain failures."""


class ReportQueueSettingsValidationError(ReportQueueSchedulerError):
    pass


class ReportQueueJobNotFoundError(ReportQueueSchedulerError):
    pass


class ReportQueueTransitionError(ReportQueueSchedulerError):
    pass


class ReportQueueConfirmationRequiredError(ReportQueueSchedulerError):
    pass


@dataclass(frozen=True)
class PromotionResult:
    approved_to_active: int = 0
    approved_to_automatic: int = 0
    automatic_to_active: int = 0


SETTING_FIELDS = (
    "processing_concurrency",
    "active_queue_capacity",
    "automatic_wait_capacity",
    "pdf_concurrency",
    "processing_paused",
    "promotion_paused",
)


def validate_queue_settings(settings: ReportQueueSetting) -> None:
    integer_fields = (
        "processing_concurrency",
        "active_queue_capacity",
        "automatic_wait_capacity",
        "pdf_concurrency",
    )
    if any(type(getattr(settings, field)) is not int for field in integer_fields):
        raise ReportQueueSettingsValidationError("调度数量设置必须为整数")
    if (
        type(settings.processing_paused) is not bool
        or type(settings.promotion_paused) is not bool
    ):
        raise ReportQueueSettingsValidationError("暂停设置必须为布尔值")
    if settings.processing_concurrency < 1:
        raise ReportQueueSettingsValidationError("同时处理报告数必须至少为 1")
    if settings.active_queue_capacity < settings.processing_concurrency:
        raise ReportQueueSettingsValidationError("执行队列容量不能小于同时处理报告数")
    if settings.automatic_wait_capacity < 0:
        raise ReportQueueSettingsValidationError("自动候补容量不能为负数")
    if settings.pdf_concurrency < 1:
        raise ReportQueueSettingsValidationError("PDF 转换并发必须至少为 1")
    if settings.pdf_concurrency > settings.processing_concurrency:
        raise ReportQueueSettingsValidationError("PDF 转换并发不能大于同时处理报告数")


def load_queue_settings(db: Session) -> ReportQueueSetting:
    settings = get_report_queue_settings(db)
    return settings if settings is not None else ReportQueueSetting(
        id=1,
        processing_concurrency=2,
        active_queue_capacity=50,
        automatic_wait_capacity=200,
        pdf_concurrency=1,
        processing_paused=False,
        promotion_paused=False,
    )


def update_queue_settings(
    db: Session,
    *,
    updated_by: str,
    confirm_processing_increase: bool | None = None,
    commit: bool = True,
    **changes: int | bool,
) -> ReportQueueSetting:
    unknown = set(changes) - set(SETTING_FIELDS)
    if unknown:
        raise ReportQueueSettingsValidationError(f"不支持的调度设置：{', '.join(sorted(unknown))}")
    try:
        settings = lock_report_queue_settings(db)
        requested_processing = changes.get("processing_concurrency", settings.processing_concurrency)
        if requested_processing > settings.processing_concurrency and confirm_processing_increase is False:
            raise ReportQueueConfirmationRequiredError("提高同时处理报告数需要确认服务器资源风险")
        for field, value in changes.items():
            setattr(settings, field, value)
        validate_queue_settings(settings)
        settings.updated_by = updated_by
        _promote_waiting_jobs_locked(db, settings)
        if commit:
            db.commit()
            db.refresh(settings)
        else:
            db.flush()
        return settings
    except Exception:
        db.rollback()
        raise


def place_delivery_job(db: Session, job_id: int) -> ReportDeliveryJob:
    """Place one unassigned queued job while holding the singleton settings lock."""

    try:
        settings = lock_report_queue_settings(db)
        validate_queue_settings(settings)
        _promote_waiting_jobs_locked(db, settings)
        job = report_queue_repo.get_delivery_job_for_update(db, job_id)
        if job is None:
            raise ReportQueueJobNotFoundError(f"报告任务 {job_id} 不存在")
        if job.status != ReportDeliveryStatus.queued.value:
            raise ReportQueueTransitionError("只有 queued 任务可以进入调度队列")
        if job.queue_state is not None:
            raise ReportQueueTransitionError("报告任务已经进入调度队列")

        active_count = report_queue_repo.count_jobs_in_state(db, ReportQueueState.active)
        automatic_count = report_queue_repo.count_jobs_in_state(
            db,
            ReportQueueState.automatic_waiting,
        )
        if active_count < settings.active_queue_capacity:
            report_queue_repo.assign_queue_state(job, ReportQueueState.active)
        elif automatic_count < settings.automatic_wait_capacity:
            report_queue_repo.assign_queue_state(job, ReportQueueState.automatic_waiting)
        else:
            report_queue_repo.assign_queue_state(job, ReportQueueState.manual_review)
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def place_delivery_job_in_transaction(db: Session, job_id: int) -> ReportDeliveryJob:
    """Place a freshly flushed job without committing the caller's transaction."""
    settings = lock_report_queue_settings(db)
    validate_queue_settings(settings)
    _promote_waiting_jobs_locked(db, settings)
    job = report_queue_repo.get_delivery_job_for_update(db, job_id)
    if job is None:
        raise ReportQueueJobNotFoundError(f"报告任务 {job_id} 不存在")
    if job.status != ReportDeliveryStatus.queued.value or job.queue_state is not None:
        raise ReportQueueTransitionError("任务不能重复进入调度队列")
    active_count = report_queue_repo.count_jobs_in_state(db, ReportQueueState.active)
    automatic_count = report_queue_repo.count_jobs_in_state(db, ReportQueueState.automatic_waiting)
    if active_count < settings.active_queue_capacity:
        state = ReportQueueState.active
    elif automatic_count < settings.automatic_wait_capacity:
        state = ReportQueueState.automatic_waiting
    else:
        state = ReportQueueState.manual_review
    report_queue_repo.assign_queue_state(job, state)
    db.flush()
    return job


def claim_next_job_locked(db: Session, *, at: datetime | None = None) -> ReportDeliveryJob | None:
    """Globally claim one job while serializing on settings row 1."""
    settings = lock_report_queue_settings(db)
    validate_queue_settings(settings)
    if settings.processing_paused:
        db.commit()
        return None
    if report_queue_repo.count_processing_jobs(db) >= settings.processing_concurrency:
        db.commit()
        return None
    job = report_queue_repo.next_claimable_active_job_for_update(db, at=at or now())
    if job is None:
        db.commit()
        return None
    job.status = ReportDeliveryStatus.processing.value
    job.processing_stage = "initializing"
    job.locked_at = at or now()
    job.lock_token = uuid.uuid4().hex
    job.attempts += 1
    db.commit()
    db.refresh(job)
    return job


def acquire_pdf_slot(db: Session, job_id: int, lock_token: str) -> bool:
    settings = lock_report_queue_settings(db)
    validate_queue_settings(settings)
    job = report_queue_repo.get_delivery_job_for_update(db, job_id)
    if (
        job is None
        or job.status != ReportDeliveryStatus.processing.value
        or job.lock_token != lock_token
    ):
        db.rollback()
        return False
    if report_queue_repo.count_pdf_jobs(db) >= settings.pdf_concurrency:
        job.processing_stage = "waiting_pdf"
        db.commit()
        return False
    job.processing_stage = "pdf"
    db.commit()
    return True


def finish_job(
    db: Session,
    job_id: int,
    lock_token: str,
    *,
    status: str,
    error: str | None = None,
    run_after: datetime | None = None,
) -> bool:
    """Lease-fenced transition that releases capacity and promotes waiters."""
    settings = lock_report_queue_settings(db)
    job = report_queue_repo.get_delivery_job_for_update(db, job_id)
    if (
        job is None
        or job.status != ReportDeliveryStatus.processing.value
        or job.lock_token != lock_token
    ):
        db.rollback()
        return False
    job.status = status
    job.last_error = error
    job.locked_at = None
    job.lock_token = None
    job.processing_stage = None
    if run_after is not None:
        job.run_after = run_after
    if status in (ReportDeliveryStatus.sent.value, ReportDeliveryStatus.cancelled.value):
        job.queue_state = None
    elif status == ReportDeliveryStatus.failed.value:
        job.queue_state = ReportQueueState.manual_review.value
    _promote_waiting_jobs_locked(db, settings)
    db.commit()
    return True


def promote_waiting_jobs(db: Session) -> PromotionResult:
    try:
        settings = lock_report_queue_settings(db)
        validate_queue_settings(settings)
        result = _promote_waiting_jobs_locked(db, settings)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def approve_manual_jobs(
    db: Session,
    job_ids: list[int],
    *,
    approved_by: str,
    approved_at: datetime | None = None,
    commit: bool = True,
) -> list[ReportDeliveryJob]:
    normalized_ids = sorted(set(job_ids))
    if not normalized_ids:
        return []
    try:
        settings = lock_report_queue_settings(db)
        validate_queue_settings(settings)
        jobs = report_queue_repo.get_delivery_jobs_for_update(db, normalized_ids)
        _require_all_jobs(jobs, normalized_ids)
        if any(job.queue_state != ReportQueueState.manual_review.value for job in jobs):
            raise ReportQueueTransitionError("只有人工审核区任务可以批准")
        approval_time = approved_at or now()
        for job in jobs:
            job.approved_at = approval_time
            job.approved_by = approved_by
            job.status = ReportDeliveryStatus.queued.value
            job.attempts = 0
            job.run_after = approval_time
            job.last_error = None
            report_queue_repo.assign_queue_state(job, ReportQueueState.approved_waiting)
        db.flush()
        _promote_waiting_jobs_locked(db, settings)
        if commit:
            db.commit()
            for job in jobs:
                db.refresh(job)
        return jobs
    except Exception:
        db.rollback()
        raise


def reject_review_jobs(
    db: Session,
    job_ids: list[int],
    *,
    rejected_by: str,
    reason: str | None = None,
    commit: bool = True,
) -> list[ReportDeliveryJob]:
    normalized_ids = sorted(set(job_ids))
    if not normalized_ids:
        return []
    try:
        settings = lock_report_queue_settings(db)
        validate_queue_settings(settings)
        jobs = report_queue_repo.get_delivery_jobs_for_update(db, normalized_ids)
        _require_all_jobs(jobs, normalized_ids)
        allowed = {ReportQueueState.manual_review.value, ReportQueueState.approved_waiting.value}
        if any(job.queue_state not in allowed for job in jobs):
            raise ReportQueueTransitionError("只有人工审核或已批准等待任务可以拒绝")
        detail = str(reason or "").strip() or "管理员拒绝执行"
        for job in jobs:
            job.status = ReportDeliveryStatus.cancelled.value
            job.last_error = f"管理员 {rejected_by} 拒绝：{detail}"
            job.processing_stage = None
            report_queue_repo.assign_queue_state(job, None)
        if commit:
            db.commit()
            for job in jobs:
                db.refresh(job)
        return jobs
    except Exception:
        db.rollback()
        raise


def _promote_waiting_jobs_locked(db: Session, settings: ReportQueueSetting) -> PromotionResult:
    if settings.promotion_paused:
        return PromotionResult()

    active_slots = max(
        settings.active_queue_capacity
        - report_queue_repo.count_jobs_in_state(db, ReportQueueState.active),
        0,
    )
    approved_to_active = report_queue_repo.list_waiting_jobs_for_update(
        db,
        ReportQueueState.approved_waiting,
        limit=active_slots,
    )
    for job in approved_to_active:
        report_queue_repo.assign_queue_state(job, ReportQueueState.active)
    db.flush()

    active_slots -= len(approved_to_active)
    automatic_to_active = report_queue_repo.list_waiting_jobs_for_update(
        db,
        ReportQueueState.automatic_waiting,
        limit=active_slots,
    )
    for job in automatic_to_active:
        report_queue_repo.assign_queue_state(job, ReportQueueState.active)
    db.flush()

    automatic_slots = max(
        settings.automatic_wait_capacity
        - report_queue_repo.count_jobs_in_state(db, ReportQueueState.automatic_waiting),
        0,
    )
    approved_to_automatic = report_queue_repo.list_waiting_jobs_for_update(
        db,
        ReportQueueState.approved_waiting,
        limit=automatic_slots,
    )
    for job in approved_to_automatic:
        report_queue_repo.assign_queue_state(job, ReportQueueState.automatic_waiting)
    db.flush()

    return PromotionResult(
        approved_to_active=len(approved_to_active),
        approved_to_automatic=len(approved_to_automatic),
        automatic_to_active=len(automatic_to_active),
    )


def _require_all_jobs(jobs: list[ReportDeliveryJob], job_ids: list[int]) -> None:
    found = {job.id for job in jobs}
    missing = [job_id for job_id in job_ids if job_id not in found]
    if missing:
        raise ReportQueueJobNotFoundError(f"报告任务不存在：{', '.join(map(str, missing))}")

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models import (
    ReportDeliveryJob,
    ReportDeliveryStatus,
    ReportQueueSetting,
    ReportQueueState,
)
from app.models import CompanyLead, DiagnosisSubmission, OperationLog, Report, Role, User
from app.service.system_setting_service import approve_report_queue_jobs, load_report_queue_overview, reject_report_queue_jobs
from app.service.report_queue_scheduler import (
    ReportQueueSettingsValidationError,
    approve_manual_jobs,
    load_queue_settings,
    place_delivery_job,
    reject_review_jobs,
    update_queue_settings,
)


@pytest.fixture()
def db(tmp_path) -> Session:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'scheduler.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _job(db: Session, number: int) -> ReportDeliveryJob:
    job = ReportDeliveryJob(
        lead_id=number,
        submission_id=number,
        report_id=number,
        recipient_email=f"customer-{number}@example.com",
        status=ReportDeliveryStatus.queued.value,
        created_at=datetime(2026, 1, 1) + timedelta(seconds=number),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _state_counts(db: Session) -> dict[str | None, int]:
    counts: dict[str | None, int] = {}
    for job in db.query(ReportDeliveryJob).all():
        counts[job.queue_state] = counts.get(job.queue_state, 0) + 1
    return counts


def _persisted_job(db: Session, number: int, *, state: str) -> ReportDeliveryJob:
    lead = CompanyLead(company_name=f"合成公司 {number}")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title=f"合成报告 {number}", html_content="<p>synthetic</p>")
    db.add(report)
    db.flush()
    job = ReportDeliveryJob(
        lead_id=lead.id,
        submission_id=submission.id,
        report_id=report.id,
        recipient_email=f"synthetic-{number}@example.com",
        status=ReportDeliveryStatus.failed.value,
        queue_state=state,
        attempts=3,
        last_error="合成失败原因",
        created_at=datetime(2026, 1, 1) + timedelta(seconds=number),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_overview_and_manual_actions_are_audited(db: Session) -> None:
    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    db.add(user)
    db.commit()
    first = _persisted_job(db, 101, state=ReportQueueState.manual_review.value)
    second = _persisted_job(db, 102, state=ReportQueueState.manual_review.value)
    overview = load_report_queue_overview(db)
    assert overview["queue_state_counts"]["manual_review"] == 2
    assert [row["company_name"] for row in overview["manual_review_jobs"]] == ["合成公司 101", "合成公司 102"]
    assert overview["approximate_drain_minutes"] == 0.0

    assert approve_report_queue_jobs(db, [first.id], user=user) == [first.id]
    assert reject_report_queue_jobs(db, [second.id], user=user, reason="不符合执行条件") == [second.id]
    db.expire_all()
    assert db.get(ReportDeliveryJob, first.id).queue_state in {
        ReportQueueState.active.value, ReportQueueState.automatic_waiting.value, ReportQueueState.approved_waiting.value
    }
    assert db.get(ReportDeliveryJob, second.id).status == ReportDeliveryStatus.cancelled.value
    actions = [row.action for row in db.query(OperationLog).order_by(OperationLog.id).all()]
    assert actions == ["approve_report_queue_jobs", "reject_report_queue_jobs"]


def test_default_settings_and_251_job_distribution(db: Session) -> None:
    transient_defaults = load_queue_settings(db)
    assert transient_defaults.processing_concurrency == 2
    assert transient_defaults.active_queue_capacity == 50
    assert transient_defaults.automatic_wait_capacity == 200
    assert transient_defaults.pdf_concurrency == 1

    for number in range(1, 252):
        job = _job(db, number)
        place_delivery_job(db, job.id)

    settings = db.get(ReportQueueSetting, 1)
    assert settings is not None
    assert (
        settings.processing_concurrency,
        settings.active_queue_capacity,
        settings.automatic_wait_capacity,
        settings.pdf_concurrency,
        settings.processing_paused,
        settings.promotion_paused,
    ) == (2, 50, 200, 1, False, False)
    assert _state_counts(db) == {
        ReportQueueState.active.value: 50,
        ReportQueueState.automatic_waiting.value: 200,
        ReportQueueState.manual_review.value: 1,
    }


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"processing_concurrency": 3, "active_queue_capacity": 2}, "执行队列容量"),
        ({"processing_concurrency": 2, "pdf_concurrency": 3}, "PDF 转换并发"),
        ({"processing_concurrency": 0}, "同时处理报告数"),
        ({"automatic_wait_capacity": -1}, "自动候补容量"),
        ({"processing_concurrency": True}, "必须为整数"),
    ],
)
def test_settings_validation_rolls_back_invalid_values(
    db: Session,
    changes: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ReportQueueSettingsValidationError, match=message):
        update_queue_settings(db, updated_by="admin@example.com", **changes)

    settings = db.get(ReportQueueSetting, 1)
    if settings is not None:
        assert settings.processing_concurrency == 2
        assert settings.active_queue_capacity == 50
        assert settings.automatic_wait_capacity == 200
        assert settings.pdf_concurrency == 1


def test_manual_review_does_not_auto_release_after_capacity_increase(db: Session) -> None:
    update_queue_settings(
        db,
        updated_by="admin@example.com",
        processing_concurrency=1,
        active_queue_capacity=1,
        automatic_wait_capacity=1,
        pdf_concurrency=1,
    )
    jobs = []
    for number in range(1, 4):
        job = _job(db, number)
        jobs.append(place_delivery_job(db, job.id))
    assert [job.queue_state for job in jobs] == [
        ReportQueueState.active.value,
        ReportQueueState.automatic_waiting.value,
        ReportQueueState.manual_review.value,
    ]

    update_queue_settings(
        db,
        updated_by="admin@example.com",
        processing_concurrency=2,
        active_queue_capacity=2,
        automatic_wait_capacity=2,
    )
    db.expire_all()

    assert (
        db.get(ReportDeliveryJob, jobs[1].id).queue_state
        == ReportQueueState.active.value
    )
    assert (
        db.get(ReportDeliveryJob, jobs[2].id).queue_state
        == ReportQueueState.manual_review.value
    )


def test_approved_job_has_priority_before_new_placement(db: Session) -> None:
    update_queue_settings(
        db,
        updated_by="admin@example.com",
        processing_concurrency=1,
        active_queue_capacity=1,
        automatic_wait_capacity=1,
        pdf_concurrency=1,
    )
    first = place_delivery_job(db, _job(db, 1).id)
    automatic = place_delivery_job(db, _job(db, 2).id)
    manual = place_delivery_job(db, _job(db, 3).id)
    approved = approve_manual_jobs(
        db,
        [manual.id],
        approved_by="admin@example.com",
        approved_at=datetime(2026, 1, 2),
    )[0]
    assert approved.queue_state == ReportQueueState.approved_waiting.value

    first.status = ReportDeliveryStatus.sent.value
    first.queue_state = None
    db.commit()
    newcomer = place_delivery_job(db, _job(db, 4).id)
    db.expire_all()

    assert (
        db.get(ReportDeliveryJob, approved.id).queue_state
        == ReportQueueState.active.value
    )
    assert (
        db.get(ReportDeliveryJob, automatic.id).queue_state
        == ReportQueueState.automatic_waiting.value
    )
    assert (
        db.get(ReportDeliveryJob, newcomer.id).queue_state
        == ReportQueueState.manual_review.value
    )


def test_approval_fills_available_tiers_without_exceeding_capacities(db: Session) -> None:
    update_queue_settings(
        db,
        updated_by="admin@example.com",
        processing_concurrency=1,
        active_queue_capacity=1,
        automatic_wait_capacity=1,
        pdf_concurrency=1,
    )
    active = place_delivery_job(db, _job(db, 1).id)
    automatic = place_delivery_job(db, _job(db, 2).id)
    manual_jobs = [place_delivery_job(db, _job(db, number).id) for number in (3, 4)]

    active.status = ReportDeliveryStatus.sent.value
    active.queue_state = None
    automatic.status = ReportDeliveryStatus.sent.value
    automatic.queue_state = None
    db.commit()
    approved = approve_manual_jobs(
        db,
        [job.id for job in manual_jobs],
        approved_by="admin@example.com",
    )

    assert {job.queue_state for job in approved} == {
        ReportQueueState.active.value,
        ReportQueueState.automatic_waiting.value,
    }
    assert _state_counts(db)[ReportQueueState.active.value] == 1
    assert _state_counts(db)[ReportQueueState.automatic_waiting.value] == 1


def test_rejection_cancels_review_task_and_removes_queue_state(db: Session) -> None:
    update_queue_settings(
        db,
        updated_by="admin@example.com",
        processing_concurrency=1,
        active_queue_capacity=1,
        automatic_wait_capacity=0,
        pdf_concurrency=1,
    )
    place_delivery_job(db, _job(db, 1).id)
    review = place_delivery_job(db, _job(db, 2).id)

    rejected = reject_review_jobs(
        db,
        [review.id],
        rejected_by="admin@example.com",
        reason="资料不完整",
    )[0]

    assert rejected.status == ReportDeliveryStatus.cancelled.value
    assert rejected.queue_state is None
    assert rejected.last_error == "管理员 admin@example.com 拒绝：资料不完整"

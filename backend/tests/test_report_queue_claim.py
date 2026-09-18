import asyncio
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CompanyLead, DiagnosisSubmission, Report, ReportDeliveryJob, ReportQueueSetting, ReportStatus
from app.service import report_queue
from app.service.report_queue import (
    _reclaim_stale_jobs,
    _touch_lease,
    _try_claim_job,
    claim_next_job,
    enqueue_report_delivery,
    process_report_delivery_job,
)
from app.service.report_queue_scheduler import acquire_pdf_slot, finish_job
from app.utils.time_utils import utc_now


def create_db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def seed_queued_job(db: Session) -> ReportDeliveryJob:
    lead = CompanyLead(company_name="Example")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="T", html_content="", status=ReportStatus.generated.value)
    db.add(report)
    db.flush()
    job = ReportDeliveryJob(
        lead_id=lead.id,
        submission_id=submission.id,
        report_id=report.id,
        recipient_email="a@example.com",
        status="queued",
        queue_state="active",
        run_after=utc_now() - timedelta(minutes=1),
    )
    db.add(job)
    db.commit()
    return job


def test_try_claim_rejects_second_claim():
    db, engine = create_db()
    job = seed_queued_job(db)

    assert _try_claim_job(db, job.id, utc_now()) is True
    assert _try_claim_job(db, job.id, utc_now()) is False
    db.close()
    engine.dispose()


def test_claim_issues_lease_token():
    """认领必须签发一次性租约 token，供心跳续约与终态条件写入使用。"""
    db, engine = create_db()
    job = seed_queued_job(db)

    assert _try_claim_job(db, job.id, utc_now()) is True
    db.refresh(job)
    assert job.status == "processing"
    assert job.lock_token and len(job.lock_token) >= 16
    assert job.locked_at is not None
    db.close()
    engine.dispose()


def test_stale_timeout_exceeds_pipeline_worst_case():
    """回收阈值必须大于流水线最大耗时（检索 + 报告生成 + PDF + 邮件），
    否则执行中的任务会被重新入队，导致重复生成、重复邮件。"""
    assert report_queue.STALE_PROCESSING_TIMEOUT >= timedelta(minutes=15)


def test_stale_reclaim_requeues_and_clears_lease():
    """超过阈值未续约的处理中任务被原子回收：重新入队并清空租约。"""
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.locked_at = utc_now() - timedelta(minutes=30)
    job.lock_token = "old-token"
    job.attempts = 1
    db.commit()

    assert _reclaim_stale_jobs(db) == 1
    db.refresh(job)
    assert job.status == "queued"
    assert job.lock_token is None
    assert job.locked_at is None
    assert "重新加入队列" in job.last_error
    db.close()
    engine.dispose()


def test_stale_reclaim_marks_exhausted_job_failed():
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.locked_at = utc_now() - timedelta(minutes=30)
    job.lock_token = "old-token"
    job.attempts = job.max_attempts
    db.commit()

    assert _reclaim_stale_jobs(db) == 1
    db.refresh(job)
    assert job.status == "failed"
    assert job.lock_token is None
    assert "已达到最大重试次数" in job.last_error
    db.close()
    engine.dispose()


def test_stale_reclaim_is_concurrent_safe():
    """两个回收者并发时，条件 UPDATE 保证只有第一个能改掉状态。"""
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.locked_at = utc_now() - timedelta(minutes=30)
    job.lock_token = "old-token"
    db.commit()

    other = Session(engine)
    assert _reclaim_stale_jobs(db) == 1
    # 第一个回收者已把状态改掉，第二个回收者的条件更新影响 0 行
    assert _reclaim_stale_jobs(other) == 0
    other.close()
    db.close()
    engine.dispose()


def test_touch_lease_requires_matching_token():
    """续约是条件更新：token 不匹配或已被回收清空时影响 0 行。"""
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.locked_at = utc_now()
    job.lock_token = "my-token"
    db.commit()

    assert _touch_lease(db, job.id, "my-token") == 1
    assert _touch_lease(db, job.id, "other-token") == 0

    job.lock_token = None  # 模拟被回收后 token 被清空
    db.commit()
    assert _touch_lease(db, job.id, "my-token") == 0
    db.close()
    engine.dispose()


def test_report_generation_failure_is_requeued_with_backoff(monkeypatch):
    """AI 报告生成失败与检索失败一样按 attempts 退避重试，而非直接终态。"""
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.attempts = 1
    job.locked_at = utc_now()
    db.commit()
    monkeypatch.setattr(report_queue, "SessionLocal", lambda: Session(engine))

    async def fake_research(session, report):
        return {"company_overview": "公开信息", "sources": [{"title": "官网", "url": "https://example.com"}]}

    async def fail_generate(session, report):
        report.status = ReportStatus.failed.value
        report.generation_error = "AI 报告生成失败：结构化校验未通过"

    monkeypatch.setattr(report_queue, "research_company", fake_research)
    monkeypatch.setattr(report_queue, "generate_report_content", fail_generate)

    assert asyncio.run(process_report_delivery_job(job.id)) is False

    verify = Session(engine)
    persisted_job = verify.get(ReportDeliveryJob, job.id)
    persisted_report = verify.get(Report, job.report_id)
    assert persisted_job.status == "queued"
    assert persisted_job.lock_token is None
    assert persisted_job.locked_at is None
    assert persisted_job.run_after > utc_now()
    assert "自动重试" in persisted_job.last_error
    assert persisted_report.status == ReportStatus.pending.value
    verify.close()
    db.close()
    engine.dispose()
def test_report_generation_failure_exhausts_to_manual_review(monkeypatch):
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.attempts = job.max_attempts
    job.locked_at = utc_now()
    db.commit()
    monkeypatch.setattr(report_queue, "SessionLocal", lambda: Session(engine))

    async def fake_research(session, report):
        return {"company_overview": "公开信息", "sources": [{"title": "官网", "url": "https://example.com"}]}

    async def fail_generate(session, report):
        report.status = ReportStatus.failed.value
        report.generation_error = "AI 报告生成失败：结构化校验未通过"

    monkeypatch.setattr(report_queue, "research_company", fake_research)
    monkeypatch.setattr(report_queue, "generate_report_content", fail_generate)

    assert asyncio.run(process_report_delivery_job(job.id)) is False

    verify = Session(engine)
    persisted_job = verify.get(ReportDeliveryJob, job.id)
    persisted_report = verify.get(Report, job.report_id)
    assert persisted_job.status == "failed"
    assert "待人工审核" in persisted_job.last_error
    assert persisted_report.status == ReportStatus.failed.value
    verify.close()
    db.close()
    engine.dispose()


def test_claim_next_job_returns_none_when_already_claimed():
    db, engine = create_db()
    seed_queued_job(db)

    claimed = claim_next_job(db)
    assert claimed is not None
    assert claim_next_job(db) is None
    db.close()
    engine.dispose()


def test_database_global_processing_limit_and_pause_apply_across_sessions():
    db, engine = create_db()
    first = seed_queued_job(db)
    second = ReportDeliveryJob(
        lead_id=first.lead_id,
        submission_id=first.submission_id,
        report_id=first.report_id,
        recipient_email="second@example.com",
        status="queued",
        queue_state="active",
        run_after=utc_now() - timedelta(minutes=1),
    )
    db.add(second)
    db.commit()
    settings = ReportQueueSetting(id=1)
    db.add(settings)
    db.flush()
    settings.processing_concurrency = 1
    settings.active_queue_capacity = 2
    db.commit()

    worker_one = Session(engine)
    worker_two = Session(engine)
    claimed = claim_next_job(worker_one)
    assert claimed is not None
    assert claim_next_job(worker_two) is None

    token = worker_one.get(ReportDeliveryJob, claimed.id).lock_token
    assert finish_job(worker_one, claimed.id, token, status="sent") is True
    settings = worker_two.get(ReportQueueSetting, 1)
    settings.processing_paused = True
    worker_two.commit()
    assert claim_next_job(worker_one) is None
    settings = worker_two.get(ReportQueueSetting, 1)
    settings.processing_paused = False
    worker_two.commit()
    assert claim_next_job(worker_one).id == second.id
    worker_one.close()
    worker_two.close()
    db.close()
    engine.dispose()


def test_database_global_pdf_slot_limit_across_sessions():
    db, engine = create_db()
    first = seed_queued_job(db)
    second = ReportDeliveryJob(
        lead_id=first.lead_id,
        submission_id=first.submission_id,
        report_id=first.report_id,
        recipient_email="second@example.com",
        status="processing",
        queue_state="active",
        processing_stage="report",
        lock_token="second-token",
        locked_at=utc_now(),
    )
    first.status = "processing"
    first.processing_stage = "report"
    first.lock_token = "first-token"
    first.locked_at = utc_now()
    db.add(second)
    db.commit()

    worker_one = Session(engine)
    worker_two = Session(engine)
    assert acquire_pdf_slot(worker_one, first.id, "first-token") is True
    assert acquire_pdf_slot(worker_two, second.id, "second-token") is False
    assert worker_two.get(ReportDeliveryJob, second.id).processing_stage == "waiting_pdf"
    assert finish_job(worker_one, first.id, "first-token", status="sent") is True
    assert acquire_pdf_slot(worker_two, second.id, "second-token") is True
    worker_one.close()
    worker_two.close()
    db.close()
    engine.dispose()


def test_claim_next_job_orders_active_candidates_fifo():
    db, engine = create_db()
    first_job = seed_queued_job(db)
    second_job = ReportDeliveryJob(
        lead_id=first_job.lead_id,
        submission_id=first_job.submission_id,
        report_id=first_job.report_id,
        recipient_email="b@example.com",
        status="queued",
        queue_state="active",
        run_after=utc_now() - timedelta(minutes=1),
    )
    db.add(second_job)
    db.commit()

    claimed = claim_next_job(db)

    assert claimed is not None
    assert claimed.id == first_job.id
    db.close()
    engine.dispose()


def test_enqueue_resends_with_new_job_when_previous_is_sent():
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "sent"
    job.sent_at = utc_now()
    db.commit()

    report = job.report
    enqueued = enqueue_report_delivery(db, report, "b@example.com")

    assert enqueued.id != job.id
    assert enqueued.recipient_email == "b@example.com"
    db.close()
    engine.dispose()


def test_email_delivery_failure_is_retried_and_not_marked_sent(monkeypatch):
    db, engine = create_db()
    job = seed_queued_job(db)

    monkeypatch.setattr(report_queue, "SessionLocal", lambda: Session(engine))

    async def fake_research(session, report):
        return {"company_overview": "公开信息", "sources": [{"title": "官网", "url": "https://example.com"}]}

    async def fake_generate(session, report):
        report.status = ReportStatus.generated.value
        report.html_content = "<p>已生成报告</p>"
        report.summary_json = "{}"
        return report

    async def fake_pdf(report):
        return b"pdf"

    def fail_email(*args, **kwargs):
        raise RuntimeError("SMTP unavailable")

    monkeypatch.setattr(report_queue, "research_company", fake_research)
    monkeypatch.setattr(report_queue, "generate_report_content", fake_generate)
    monkeypatch.setattr(report_queue, "render_report_pdf_bytes", fake_pdf)
    monkeypatch.setattr(report_queue, "send_report_pdf_email", fail_email)

    assert asyncio.run(process_report_delivery_job(job.id)) is False

    verify = Session(engine)
    persisted_report = verify.get(Report, job.report_id)
    persisted_job = verify.get(ReportDeliveryJob, job.id)
    assert persisted_report.status == ReportStatus.generated.value
    assert persisted_report.html_content == "<p>已生成报告</p>"
    assert persisted_job.status == "queued"
    assert persisted_job.last_error == "邮件发送失败：SMTP unavailable"
    verify.close()
    db.close()
    engine.dispose()


def test_research_failure_is_requeued_for_automatic_recovery(monkeypatch):
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.attempts = 1
    job.locked_at = utc_now()
    db.commit()
    monkeypatch.setattr(report_queue, "SessionLocal", lambda: Session(engine))

    async def fail_research(session, report):
        report.generation_error = "公司情报检索失败：服务暂时不可用"
        return None

    monkeypatch.setattr(report_queue, "research_company", fail_research)

    assert asyncio.run(process_report_delivery_job(job.id)) is False

    verify = Session(engine)
    persisted_job = verify.get(ReportDeliveryJob, job.id)
    persisted_report = verify.get(Report, job.report_id)
    assert persisted_job.status == "queued"
    assert persisted_job.locked_at is None
    assert persisted_job.run_after > utc_now()
    assert "自动重试" in persisted_job.last_error
    assert persisted_report.status == "pending"
    verify.close()
    db.close()
    engine.dispose()


def test_research_failure_moves_to_manual_review_after_retries(monkeypatch):
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "processing"
    job.attempts = job.max_attempts
    job.locked_at = utc_now()
    db.commit()
    monkeypatch.setattr(report_queue, "SessionLocal", lambda: Session(engine))

    async def fail_research(session, report):
        report.generation_error = "公司情报检索失败：服务暂时不可用"
        return None

    monkeypatch.setattr(report_queue, "research_company", fail_research)

    assert asyncio.run(process_report_delivery_job(job.id)) is False

    verify = Session(engine)
    persisted_job = verify.get(ReportDeliveryJob, job.id)
    persisted_report = verify.get(Report, job.report_id)
    assert persisted_job.status == "failed"
    assert persisted_report.status == "failed"
    assert persisted_report.research_status == "review"
    assert "待人工审核" in persisted_job.last_error
    verify.close()
    db.close()
    engine.dispose()

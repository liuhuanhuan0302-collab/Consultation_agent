from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CompanyLead, DiagnosisSubmission, Report, ReportDeliveryJob, ReportStatus
from app.service import report_queue
from app.service.report_queue import _try_claim_job, claim_next_job, enqueue_report_delivery
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


def test_claim_next_job_returns_none_when_already_claimed():
    db, engine = create_db()
    seed_queued_job(db)

    claimed = claim_next_job(db)
    assert claimed is not None
    assert claim_next_job(db) is None
    db.close()
    engine.dispose()


def test_claim_next_job_tries_the_next_candidate_after_a_race(monkeypatch):
    db, engine = create_db()
    first_job = seed_queued_job(db)
    second_job = ReportDeliveryJob(
        lead_id=first_job.lead_id,
        submission_id=first_job.submission_id,
        report_id=first_job.report_id,
        recipient_email="b@example.com",
        status="queued",
        run_after=utc_now() - timedelta(minutes=1),
    )
    db.add(second_job)
    db.commit()

    original_try_claim = report_queue._try_claim_job
    calls = 0

    def claim_as_competing_worker(session, job_id, now):
        nonlocal calls
        calls += 1
        claimed = original_try_claim(session, job_id, now)
        return False if calls == 1 else claimed

    monkeypatch.setattr(report_queue, "_try_claim_job", claim_as_competing_worker)

    claimed = claim_next_job(db)

    assert claimed is not None
    assert claimed.id == second_job.id
    assert calls == 2
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

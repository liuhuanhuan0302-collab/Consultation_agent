from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CompanyLead, DiagnosisSubmission, Report, ReportDeliveryJob, ReportStatus
from app.service.report_queue import _try_claim_job, claim_next_job, enqueue_report_delivery


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
        run_after=datetime.utcnow() - timedelta(minutes=1),
    )
    db.add(job)
    db.commit()
    return job


def test_try_claim_rejects_second_claim():
    db, engine = create_db()
    job = seed_queued_job(db)

    assert _try_claim_job(db, job.id, datetime.utcnow()) is True
    assert _try_claim_job(db, job.id, datetime.utcnow()) is False
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


def test_enqueue_resends_with_new_job_when_previous_is_sent():
    db, engine = create_db()
    job = seed_queued_job(db)
    job.status = "sent"
    job.sent_at = datetime.utcnow()
    db.commit()

    report = job.report
    enqueued = enqueue_report_delivery(db, report, "b@example.com")

    assert enqueued.id != job.id
    assert enqueued.recipient_email == "b@example.com"
    db.close()
    engine.dispose()

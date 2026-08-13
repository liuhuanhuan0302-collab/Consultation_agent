from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin import admin_get_lead_detail
from app.database import Base
from app.models import CompanyLead, DiagnosisSubmission, Report, ReportDeliveryJob, Role, User


def test_lead_detail_uses_delivery_for_current_report_only():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    now = datetime.now()

    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    lead = CompanyLead(company_name="Example")
    db.add_all([user, lead])
    db.flush()

    old_submission = DiagnosisSubmission(lead_id=lead.id, created_at=now - timedelta(days=1))
    current_submission = DiagnosisSubmission(lead_id=lead.id, created_at=now)
    db.add_all([old_submission, current_submission])
    db.flush()

    old_report = Report(submission_id=old_submission.id, title="Old", html_content="", created_at=now - timedelta(days=1))
    current_report = Report(submission_id=current_submission.id, title="Current", html_content="", created_at=now)
    db.add_all([old_report, current_report])
    db.flush()

    db.add_all(
        [
            ReportDeliveryJob(
                lead_id=lead.id,
                submission_id=old_submission.id,
                report_id=old_report.id,
                recipient_email="old@example.com",
                status="sent",
                created_at=now + timedelta(minutes=5),
            ),
            ReportDeliveryJob(
                lead_id=lead.id,
                submission_id=current_submission.id,
                report_id=current_report.id,
                recipient_email="current@example.com",
                status="queued",
                created_at=now,
            ),
        ]
    )
    db.commit()

    detail = admin_get_lead_detail(lead.id, db=db, user=user)

    assert detail["report"]["id"] == current_report.id
    assert detail["delivery"]["recipient_email"] == "current@example.com"
    db.close()
    engine.dispose()

import asyncio
import inspect

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    CompanyLead,
    DiagnosisSubmission,
    ExportLog,
    OperationLog,
    Report,
    ReportDeliveryJob,
    Role,
    User,
)
from app.api.v1.endpoints.admin import leads as leads_endpoint
from app.schemas import LeadDiagnosticEmailUpdate
from app.service import lead_service


def create_db() -> tuple[Session, object, User]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    db.add(user)
    db.commit()
    return db, engine, user


def test_export_csv_escapes_formulas_and_records_audit():
    db, engine, user = create_db()
    db.add(CompanyLead(company_name="=HYPERLINK(\"bad\")", email="customer@example.com"))
    db.commit()

    content = lead_service.export_leads_csv(db, user)

    assert "'=HYPERLINK" in content
    assert db.query(ExportLog).filter(ExportLog.export_type == "leads").count() == 1
    assert db.query(OperationLog).filter(OperationLog.action == "export_leads").count() == 1
    db.close()
    engine.dispose()


def test_update_email_uses_latest_submission_report_and_enqueues_once():
    db, engine, user = create_db()
    lead = CompanyLead(company_name="Example", email="old@example.com")
    db.add(lead)
    db.flush()
    older = DiagnosisSubmission(lead_id=lead.id)
    latest = DiagnosisSubmission(lead_id=lead.id)
    db.add_all([older, latest])
    db.flush()
    older_report = Report(submission_id=older.id, title="Old", html_content="")
    latest_report = Report(submission_id=latest.id, title="Latest", html_content="")
    db.add_all([older_report, latest_report])
    db.commit()

    result = lead_service.update_diagnostic_email(db, user, lead.id, " NEW@Example.COM ")

    assert result.should_process_queue is True
    assert lead.email == "new@example.com"
    jobs = db.query(ReportDeliveryJob).all()
    assert len(jobs) == 1
    assert jobs[0].report_id == latest_report.id
    assert jobs[0].recipient_email == "new@example.com"
    db.close()
    engine.dispose()


def test_cached_research_keeps_existing_result_without_new_audit():
    db, engine, user = create_db()
    lead = CompanyLead(company_name="Example")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    db.add(Report(submission_id=submission.id, title="R", html_content="", company_research_json='{"ok": true}'))
    db.commit()

    result = lead_service.trigger_research(db, user, lead.id, force=False)

    assert result.status == "already_generated"
    assert result.report_id is None
    assert db.query(OperationLog).filter(OperationLog.action == "trigger_lead_research").count() == 0
    db.close()
    engine.dispose()


def test_lead_service_not_found_and_no_fastapi_dependency():
    db, engine, user = create_db()
    with pytest.raises(lead_service.LeadNotFoundError):
        lead_service.get_lead_detail(db, 999)
    with pytest.raises(lead_service.LeadNotFoundError):
        lead_service.delete_lead(db, user, 999)
    assert "fastapi" not in inspect.getsource(lead_service)
    db.close()
    engine.dispose()


def test_word_export_uses_any_sent_delivery_for_current_report(monkeypatch):
    db, engine, user = create_db()
    lead = CompanyLead(company_name="Example")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="R", html_content="")
    db.add(report)
    db.flush()
    db.add_all(
        [
            ReportDeliveryJob(lead_id=lead.id, submission_id=submission.id, report_id=report.id, recipient_email="a@example.com", status="sent"),
            ReportDeliveryJob(lead_id=lead.id, submission_id=submission.id, report_id=report.id, recipient_email="a@example.com", status="failed"),
        ]
    )
    db.commit()
    captured = {}

    def fake_generate(*_args, **kwargs):
        captured.update(kwargs)
        return b"docx"

    monkeypatch.setattr(lead_service, "generate_lead_export_docx", fake_generate)
    result = lead_service.export_lead_word(db, user, lead.id)
    assert result.document == b"docx"
    assert captured["final_report_sent"] is True
    db.close()
    engine.dispose()


def test_force_research_replaces_cached_result_and_records_audit(monkeypatch):
    db, engine, user = create_db()
    lead = CompanyLead(company_name="Example")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="R", html_content="", company_research_json='{"old": true}')
    db.add(report)
    db.commit()
    monkeypatch.setattr(lead_service, "effective_search_config", lambda _db: object())

    result = lead_service.trigger_research(db, user, lead.id, force=True)

    assert result.status == "started"
    assert result.report_id == report.id
    assert result.force is True
    assert report.research_status == "processing"
    assert db.query(OperationLog).filter(OperationLog.action == "trigger_lead_research").count() == 1
    db.close()
    engine.dispose()


def test_delete_service_preserves_audit_after_cascade():
    db, engine, user = create_db()
    lead = CompanyLead(company_name="Delete Me")
    db.add(lead)
    db.commit()
    lead_id = lead.id

    message = lead_service.delete_lead(db, user, lead_id)

    assert "Delete Me" in message
    assert db.query(CompanyLead).filter(CompanyLead.id == lead_id).first() is None
    audit = db.query(OperationLog).filter(OperationLog.action == "delete_lead").one()
    assert audit.target_id == str(lead_id)
    db.close()
    engine.dispose()


def test_email_endpoint_schedules_only_after_service_success(monkeypatch):
    async def run(result):
        monkeypatch.setattr(lead_service, "update_diagnostic_email", lambda *_args: result)
        background = BackgroundTasks()
        response = await leads_endpoint.update_lead_diagnostic_email(
            1,
            LeadDiagnosticEmailUpdate(email="new@example.com"),
            background,
            object(),
            SimpleUser(),
        )
        return response, background

    class SimpleUser:
        id = 1

    response, background = asyncio.run(
        run(lead_service.DiagnosticEmailResult("queued", True))
    )
    assert response.message == "queued"
    assert len(background.tasks) == 1

    _, background = asyncio.run(
        run(lead_service.DiagnosticEmailResult("no report", False))
    )
    assert background.tasks == []


# ── 继续生成报告并发送（企业情报已生成、报告/投递失败后的恢复入口） ──


def _failed_pipeline_fixture(db: Session, *, research_json: str | None = '{"ok": true}', lead_email="customer@example.com"):
    lead = CompanyLead(company_name="Example", email=lead_email)
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(
        submission_id=submission.id,
        title="R",
        html_content="",
        company_research_json=research_json,
        status="failed",
        generation_error="旧生成错误",
        pdf_status="failed",
    )
    db.add(report)
    db.flush()
    delivery = ReportDeliveryJob(
        lead_id=lead.id,
        submission_id=submission.id,
        report_id=report.id,
        recipient_email=lead_email,
        status="failed",
        attempts=3,
        max_attempts=3,
        last_error="自动重试已耗尽",
        locked_at=None,
    )
    db.add(delivery)
    db.commit()
    return lead, report, delivery


def test_resume_delivery_resets_failed_job_and_requeues():
    db, engine, user = create_db()
    lead, report, delivery = _failed_pipeline_fixture(db)

    result = lead_service.resume_report_delivery(db, user, lead.id)

    assert result.should_process_queue is True
    assert result.report_id == report.id
    assert report.status == "pending"
    assert report.generation_error is None
    assert report.pdf_status == "pending"
    assert delivery.status == "queued"
    assert delivery.attempts == 0
    assert delivery.last_error is None
    assert delivery.locked_at is None
    assert delivery.run_after is not None
    assert db.query(OperationLog).filter(OperationLog.action == "resume_report_delivery").count() == 1
    db.close()
    engine.dispose()


def test_resume_delivery_requires_generated_research():
    db, engine, user = create_db()
    lead, _report, _delivery = _failed_pipeline_fixture(db, research_json=None)

    with pytest.raises(lead_service.LeadValidationError):
        lead_service.resume_report_delivery(db, user, lead.id)
    db.close()
    engine.dispose()


def test_resume_delivery_rejects_active_or_sent_delivery():
    for status in ("queued", "processing", "sent"):
        db, engine, user = create_db()
        lead, _report, delivery = _failed_pipeline_fixture(db)
        delivery.status = status
        db.commit()

        with pytest.raises(lead_service.LeadValidationError):
            lead_service.resume_report_delivery(db, user, lead.id)
        db.close()
        engine.dispose()


def test_resume_delivery_creates_job_when_missing():
    db, engine, user = create_db()
    lead, report, delivery = _failed_pipeline_fixture(db)
    db.delete(delivery)
    db.commit()

    result = lead_service.resume_report_delivery(db, user, lead.id)

    assert result.should_process_queue is True
    jobs = db.query(ReportDeliveryJob).filter(ReportDeliveryJob.report_id == report.id).all()
    assert len(jobs) == 1
    assert jobs[0].status == "queued"
    assert jobs[0].attempts == 0
    assert jobs[0].recipient_email == "customer@example.com"
    db.close()
    engine.dispose()


def test_resume_delivery_requires_email_when_no_job():
    db, engine, user = create_db()
    lead, _report, delivery = _failed_pipeline_fixture(db, lead_email="")
    db.delete(delivery)
    db.commit()

    with pytest.raises(lead_service.LeadValidationError):
        lead_service.resume_report_delivery(db, user, lead.id)
    db.close()
    engine.dispose()


def test_resume_endpoint_schedules_queue_wakeup_only_after_service_success(monkeypatch):
    async def run(result):
        monkeypatch.setattr(lead_service, "resume_report_delivery", lambda *_args: result)
        background = BackgroundTasks()
        response = await leads_endpoint.resume_lead_report_delivery(
            1,
            background,
            object(),
            SimpleUser(),
        )
        return response, background

    class SimpleUser:
        id = 1

    response, background = asyncio.run(
        run(lead_service.ResumeDeliveryResult("已重新入队", True, 1))
    )
    assert response.message == "已重新入队"
    assert len(background.tasks) == 1

    _, background = asyncio.run(
        run(lead_service.ResumeDeliveryResult("无需继续", False, None))
    )
    assert background.tasks == []

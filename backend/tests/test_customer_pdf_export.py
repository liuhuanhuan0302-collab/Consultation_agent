import asyncio
from datetime import datetime
from io import BytesIO

import pytest
from pypdf import PdfWriter
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
    ReportQueueSetting,
    User,
)
from app.service import lead_service, report_queue
from app.utils.time_utils import utc_now


def valid_pdf_bytes() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(output)
    return output.getvalue()


@pytest.fixture()
def pdf_export_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(
        ReportQueueSetting(
            id=1,
            processing_concurrency=2,
            active_queue_capacity=50,
            automatic_wait_capacity=200,
            pdf_concurrency=1,
            processing_paused=False,
            promotion_paused=False,
        )
    )
    user = User(
        email="exporter@example.com",
        name="Exporter",
        role="sales",
        password_hash="hash",
    )
    db.add(user)
    db.commit()
    yield db, engine, user
    db.close()
    engine.dispose()


def add_lead_report(
    db: Session,
    *,
    status: str = "generated",
    customer_pdf_bytes: bytes | None = None,
) -> tuple[CompanyLead, Report]:
    lead = CompanyLead(company_name="测试企业", email="customer@example.com")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id, status="submitted")
    db.add(submission)
    db.flush()
    report = Report(
        submission_id=submission.id,
        title="测试企业 AI 原生转型诊断报告",
        html_content="<h2>一、执行摘要</h2>",
        summary_json='{"score":{"total":1,"max_score":2,"score_rate":0.5}}',
        status=status,
        customer_pdf_bytes=customer_pdf_bytes,
    )
    db.add(report)
    db.commit()
    return lead, report


def test_prepare_rejects_missing_or_not_ready_report_and_deduplicates(pdf_export_db):
    db, _engine, user = pdf_export_db
    lead_without_report = CompanyLead(company_name="无报告")
    db.add(lead_without_report)
    db.commit()
    with pytest.raises(lead_service.LeadReportNotFoundError):
        lead_service.prepare_lead_pdf_export(db, user, lead_without_report.id)

    pending_lead, _pending_report = add_lead_report(db, status="pending")
    with pytest.raises(lead_service.LeadValidationError):
        lead_service.prepare_lead_pdf_export(db, user, pending_lead.id)

    lead, report = add_lead_report(db)
    first = lead_service.prepare_lead_pdf_export(db, user, lead.id)
    second = lead_service.prepare_lead_pdf_export(db, user, lead.id)
    assert first.status == "queued"
    assert second.status == "queued"
    jobs = db.query(ReportDeliveryJob).filter_by(
        report_id=report.id,
        task_kind="pdf_export",
    ).all()
    assert len(jobs) == 1
    assert jobs[0].recipient_email == ""


def test_ready_prepare_and_download_validate_and_audit(pdf_export_db):
    db, _engine, user = pdf_export_db
    pdf = valid_pdf_bytes()
    lead, _report = add_lead_report(db, customer_pdf_bytes=pdf)

    prepared = lead_service.prepare_lead_pdf_export(db, user, lead.id)
    downloaded = lead_service.download_lead_pdf_export(db, user, lead.id)

    assert prepared.status == "ready"
    assert downloaded.document == pdf
    assert downloaded.filename == "测试企业_AI诊断报告.pdf"
    assert db.query(ExportLog).filter_by(export_type="lead_customer_pdf").count() == 1
    assert db.query(OperationLog).filter_by(action="export_lead_customer_pdf").count() == 1


def test_download_rejects_not_ready_artifact(pdf_export_db):
    db, _engine, user = pdf_export_db
    lead, _report = add_lead_report(db)
    with pytest.raises(lead_service.LeadConflictError, match="尚未生成"):
        lead_service.download_lead_pdf_export(db, user, lead.id)


def test_pdf_export_worker_is_email_free_and_content_preserving(pdf_export_db, monkeypatch):
    db, engine, _user = pdf_export_db
    lead, report = add_lead_report(db)
    original_html = report.html_content
    original_summary = report.summary_json
    job = ReportDeliveryJob(
        lead_id=lead.id,
        submission_id=report.submission_id,
        report_id=report.id,
        recipient_email="",
        status="processing",
        task_kind="pdf_export",
        attempts=1,
        max_attempts=3,
        locked_at=utc_now(),
        lock_token="pdf-export-lease",
        run_after=utc_now(),
        queue_state="active",
    )
    db.add(job)
    db.commit()
    pdf = valid_pdf_bytes()
    calls = {"research": 0, "generation": 0, "email": 0}
    monkeypatch.setattr(report_queue, "SessionLocal", lambda: Session(engine))

    async def forbidden_research(*_args, **_kwargs):
        calls["research"] += 1
        raise AssertionError("pdf_export must not research")

    async def forbidden_generation(*_args, **_kwargs):
        calls["generation"] += 1
        raise AssertionError("pdf_export must not regenerate content")

    async def fake_pdf(_report):
        return pdf

    monkeypatch.setattr(report_queue, "research_company", forbidden_research)
    monkeypatch.setattr(report_queue, "generate_report_content", forbidden_generation)
    monkeypatch.setattr(report_queue, "render_report_pdf_bytes", fake_pdf)
    monkeypatch.setattr(
        report_queue,
        "send_report_pdf_email",
        lambda *_args, **_kwargs: calls.__setitem__("email", calls["email"] + 1),
    )

    assert asyncio.run(report_queue.process_report_delivery_job(job.id)) is True
    db.expire_all()
    assert db.get(ReportDeliveryJob, job.id).status == "cancelled"
    persisted = db.get(Report, report.id)
    assert persisted.customer_pdf_bytes == pdf
    assert persisted.html_content == original_html
    assert persisted.summary_json == original_summary
    assert calls == {"research": 0, "generation": 0, "email": 0}


def test_normal_delivery_persists_exact_emailed_bytes(pdf_export_db, monkeypatch):
    db, engine, _user = pdf_export_db
    lead, report = add_lead_report(db)
    job = ReportDeliveryJob(
        lead_id=lead.id,
        submission_id=report.submission_id,
        report_id=report.id,
        recipient_email="customer@example.com",
        status="processing",
        task_kind="full_delivery",
        attempts=1,
        max_attempts=3,
        locked_at=utc_now(),
        lock_token="delivery-lease",
        run_after=utc_now(),
        queue_state="active",
    )
    db.add(job)
    db.commit()
    pdf = valid_pdf_bytes()
    emailed: list[bytes] = []
    monkeypatch.setattr(report_queue, "SessionLocal", lambda: Session(engine))

    async def fake_pdf(_report):
        return pdf

    monkeypatch.setattr(report_queue, "render_report_pdf_bytes", fake_pdf)
    monkeypatch.setattr(
        report_queue,
        "send_report_pdf_email",
        lambda _email, _title, attachment, _filename, **_kwargs: emailed.append(attachment),
    )

    assert asyncio.run(report_queue.process_report_delivery_job(job.id)) is True
    db.expire_all()
    assert emailed == [pdf]
    assert db.get(Report, report.id).customer_pdf_bytes == emailed[0]


def test_successful_content_regeneration_invalidates_stored_pdf(pdf_export_db, monkeypatch):
    db, engine, user = pdf_export_db
    lead, report = add_lead_report(db, customer_pdf_bytes=valid_pdf_bytes())
    started_at = datetime(2026, 9, 17, 1, 2, 3)
    report.status = "generating"
    report.generation_started_at = started_at
    db.commit()

    async def fake_candidate(_db, _report):
        return object()

    def fake_apply(_db, current_report, _candidate):
        current_report.status = "generated"
        current_report.html_content = "<h2>一、执行摘要</h2><p>新正文</p>"
        current_report.generation_error = None

    monkeypatch.setattr(lead_service, "generate_report_candidate", fake_candidate)
    monkeypatch.setattr(lead_service, "apply_report_candidate", fake_apply)
    monkeypatch.setattr(lead_service, "SessionLocal", lambda: Session(engine))

    asyncio.run(
        lead_service.run_report_regeneration_task(
            report.id,
            user.id,
            "generated",
            started_at,
        )
    )
    db.expire_all()
    persisted = db.get(Report, report.id)
    assert persisted.status == "generated"
    assert persisted.customer_pdf_bytes is None
    assert persisted.pdf_status == "pending"

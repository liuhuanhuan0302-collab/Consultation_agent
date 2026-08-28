import asyncio
import inspect
from datetime import datetime, timedelta

import pytest
from fastapi import BackgroundTasks, HTTPException
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
from app.service.reporting import ReportContentInvalidError, ReportGenerationCandidate
from app.utils.auth import AdminOnly


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


# ── 重新生成附件并发送（不重新生成 AI 正文） ──


def _failed_attachment_fixture(db: Session, *, report_status: str = "generated"):
    lead, report, delivery = _failed_pipeline_fixture(db)
    report.status = report_status
    report.html_content = "<article><h2>一、执行摘要</h2><p>已审核正文</p></article>"
    report.generation_error = None
    delivery.last_error = "PDF 附件生成失败，已转人工处理"
    db.commit()
    return lead, report, delivery


@pytest.mark.parametrize("report_status", ["generated", "fallback"])
def test_retry_attachment_delivery_requeues_without_changing_ai_body(report_status):
    db, engine, user = create_db()
    lead, report, delivery = _failed_attachment_fixture(db, report_status=report_status)
    original_html = report.html_content

    result = lead_service.retry_report_attachment_delivery(db, user, lead.id)

    assert result.should_process_queue is True
    assert report.status == report_status
    assert report.html_content == original_html
    assert report.pdf_status == "pending"
    assert delivery.status == "queued"
    assert delivery.attempts == 0
    assert delivery.last_error is None
    assert delivery.locked_at is None and delivery.lock_token is None
    assert db.query(OperationLog).filter(
        OperationLog.action == "retry_report_attachment_delivery"
    ).count() == 1
    db.close()
    engine.dispose()


@pytest.mark.parametrize("status", ["queued", "processing", "sent"])
def test_retry_attachment_delivery_rejects_duplicate_or_sent(status):
    db, engine, user = create_db()
    lead, _report, delivery = _failed_attachment_fixture(db)
    delivery.status = status
    db.commit()

    with pytest.raises(lead_service.LeadConflictError):
        lead_service.retry_report_attachment_delivery(db, user, lead.id)
    db.close()
    engine.dispose()


def test_retry_attachment_endpoint_schedules_queue_after_success(monkeypatch):
    monkeypatch.setattr(
        lead_service,
        "retry_report_attachment_delivery",
        lambda *_args: lead_service.ResumeDeliveryResult("已重新加入附件生成队列", True, 1),
    )
    background = BackgroundTasks()

    response = asyncio.run(leads_endpoint.retry_lead_report_attachment_delivery(
        1,
        background,
        object(),
        type("SimpleUser", (), {"id": 1})(),
    ))

    assert response.message == "已重新加入附件生成队列"
    assert len(background.tasks) == 1


# ── 仅重新生成 AI 报告（不生成 PDF、不创建投递任务、不发送邮件） ──


def _regeneration_fixture(db: Session):
    lead = CompanyLead(company_name="Example", email="customer@example.com")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id, status="scored", total_score=10, max_score=20)
    db.add(submission)
    db.flush()
    report = Report(
        submission_id=submission.id,
        title="R",
        html_content="<article>old</article>",
        summary_json='{"old": true}',
        company_research_json='{"evidence_version": 1}',
        status="generated",
        pdf_status="generated",
        pdf_path="old.pdf",
    )
    db.add(report)
    db.commit()
    return lead, report


def test_trigger_report_regeneration_requires_report_and_persisted_research(monkeypatch):
    db, engine, user = create_db()
    lead = CompanyLead(company_name="No report")
    db.add(lead)
    db.commit()
    with pytest.raises(lead_service.LeadReportNotFoundError):
        lead_service.trigger_report_regeneration(db, user, lead.id)

    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    db.add(Report(submission_id=submission.id, title="R", html_content="old", status="generated"))
    db.commit()
    with pytest.raises(lead_service.LeadValidationError, match="企业情报尚未生成"):
        lead_service.trigger_report_regeneration(db, user, lead.id)
    db.close()
    engine.dispose()


def test_trigger_report_regeneration_rejects_duplicate_and_active_delivery(monkeypatch):
    monkeypatch.setattr(lead_service, "_validated_persisted_research", lambda _report: {})
    fixed_now = datetime(2026, 8, 28, 10, 0, 0)
    monkeypatch.setattr(lead_service, "utc_now", lambda: fixed_now)
    for conflict in ("generating", "queued", "processing"):
        db, engine, user = create_db()
        lead, report = _regeneration_fixture(db)
        if conflict == "generating":
            report.status = "generating"
            report.generation_started_at = fixed_now - timedelta(minutes=1)
        else:
            db.add(ReportDeliveryJob(
                lead_id=lead.id,
                submission_id=report.submission_id,
                report_id=report.id,
                recipient_email="customer@example.com",
                status=conflict,
            ))
        db.commit()
        with pytest.raises(lead_service.LeadConflictError):
            lead_service.trigger_report_regeneration(db, user, lead.id)
        db.close()
        engine.dispose()


def test_report_regeneration_success_replaces_only_report_and_records_audit(monkeypatch):
    db, engine, user = create_db()
    lead, report = _regeneration_fixture(db)
    sent = ReportDeliveryJob(
        lead_id=lead.id,
        submission_id=report.submission_id,
        report_id=report.id,
        recipient_email="customer@example.com",
        status="sent",
    )
    db.add(sent)
    db.commit()
    monkeypatch.setattr(lead_service, "_validated_persisted_research", lambda _report: {})
    monkeypatch.setattr(lead_service, "SessionLocal", lambda: Session(engine))

    async def fake_candidate(_db, _report):
        return ReportGenerationCandidate(
            payload={"report_format_version": 2, "new": True},
            html_content="<article>new</article>",
            cases=(),
            messages=(),
            model_name="mock-model",
        )

    monkeypatch.setattr(lead_service, "generate_report_candidate", fake_candidate)
    result = lead_service.trigger_report_regeneration(db, user, lead.id)
    asyncio.run(lead_service.run_report_regeneration_task(
        result.report_id,
        result.user_id,
        result.previous_status,
        result.generation_started_at,
    ))
    db.expire_all()
    refreshed = db.get(Report, report.id)
    assert refreshed.status == "generated"
    assert refreshed.html_content == "<article>new</article>"
    assert refreshed.summary_json == '{"report_format_version": 2, "new": true}'
    assert refreshed.pdf_status == "pending"
    assert refreshed.pdf_path is None
    assert db.query(ReportDeliveryJob).count() == 1
    assert db.get(ReportDeliveryJob, sent.id).status == "sent"
    success_log = db.query(OperationLog).filter(OperationLog.action == "regenerate_ai_report").one()
    assert '"status": "succeeded"' in success_log.detail_json
    db.close()
    engine.dispose()


def test_report_regeneration_failure_preserves_old_snapshot(monkeypatch):
    db, engine, user = create_db()
    lead, report = _regeneration_fixture(db)
    old_values = (report.html_content, report.summary_json, report.pdf_status, report.pdf_path)
    monkeypatch.setattr(lead_service, "_validated_persisted_research", lambda _report: {})
    monkeypatch.setattr(lead_service, "SessionLocal", lambda: Session(engine))

    async def fail_candidate(_db, _report):
        raise ReportContentInvalidError("缺少第五章")

    monkeypatch.setattr(lead_service, "generate_report_candidate", fail_candidate)
    result = lead_service.trigger_report_regeneration(db, user, lead.id)
    asyncio.run(lead_service.run_report_regeneration_task(
        result.report_id,
        result.user_id,
        result.previous_status,
        result.generation_started_at,
    ))
    db.expire_all()
    refreshed = db.get(Report, report.id)
    assert refreshed.status == "generated"
    assert (refreshed.html_content, refreshed.summary_json, refreshed.pdf_status, refreshed.pdf_path) == old_values
    assert "原报告已保留" in refreshed.generation_error
    assert len(refreshed.generation_error) <= 500
    assert db.query(ReportDeliveryJob).count() == 0
    failure_log = db.query(OperationLog).filter(OperationLog.action == "regenerate_ai_report").one()
    assert '"status": "failed"' in failure_log.detail_json
    db.close()
    engine.dispose()


def test_stale_report_regeneration_recovers_fallback_and_reserves_new_lease(monkeypatch):
    db, engine, user = create_db()
    lead, report = _regeneration_fixture(db)
    fixed_now = datetime(2026, 8, 28, 10, 0, 0)
    stale_started_at = fixed_now - lead_service.REPORT_REGENERATION_STALE_TIMEOUT - timedelta(seconds=1)
    report.status = "generating"
    report.generation_started_at = stale_started_at
    db.add(OperationLog(
        user_id=user.id,
        action="trigger_report_regeneration",
        target_type="lead",
        target_id=str(lead.id),
        detail_json=(
            '{"report_id": %d, "previous_status": "fallback", '
            '"generation_started_at": "%s"}'
        ) % (report.id, stale_started_at.isoformat()),
        created_at=stale_started_at,
    ))
    db.commit()
    monkeypatch.setattr(lead_service, "utc_now", lambda: fixed_now)
    monkeypatch.setattr(lead_service, "_validated_persisted_research", lambda _report: {})

    result = lead_service.trigger_report_regeneration(db, user, lead.id)

    db.refresh(report)
    assert result.previous_status == "fallback"
    assert result.generation_started_at == fixed_now
    assert report.status == "generating"
    assert report.generation_started_at == fixed_now
    recovery = db.query(OperationLog).filter(
        OperationLog.action == "recover_stale_report_regeneration"
    ).one()
    assert '"restored_status": "fallback"' in recovery.detail_json
    reservation = db.query(OperationLog).filter(
        OperationLog.action == "trigger_report_regeneration"
    ).order_by(OperationLog.id.desc()).first()
    assert '"previous_status": "fallback"' in reservation.detail_json
    assert fixed_now.isoformat() in reservation.detail_json
    db.close()
    engine.dispose()


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_old_report_regeneration_task_cannot_write_after_lease_changes(monkeypatch, outcome):
    db, engine, user = create_db()
    lead, report = _regeneration_fixture(db)
    first_started_at = datetime(2026, 8, 28, 10, 0, 0)
    newer_started_at = first_started_at + timedelta(minutes=20)
    monkeypatch.setattr(lead_service, "utc_now", lambda: first_started_at)
    monkeypatch.setattr(lead_service, "_validated_persisted_research", lambda _report: {})
    monkeypatch.setattr(lead_service, "SessionLocal", lambda: Session(engine))
    result = lead_service.trigger_report_regeneration(db, user, lead.id)

    async def candidate_with_newer_lease(task_db, task_report):
        task_report.generation_started_at = newer_started_at
        task_db.commit()
        if outcome == "failure":
            raise ReportContentInvalidError("旧任务失败")
        return ReportGenerationCandidate(
            payload={"report_format_version": 2, "new": True},
            html_content="<article>old-task-output</article>",
            cases=(),
            messages=(),
            model_name="mock-model",
        )

    monkeypatch.setattr(lead_service, "generate_report_candidate", candidate_with_newer_lease)
    asyncio.run(lead_service.run_report_regeneration_task(
        result.report_id,
        result.user_id,
        result.previous_status,
        result.generation_started_at,
    ))

    db.expire_all()
    refreshed = db.get(Report, report.id)
    assert refreshed.status == "generating"
    assert refreshed.generation_started_at == newer_started_at
    assert refreshed.html_content == "<article>old</article>"
    assert refreshed.generation_error is None
    assert db.query(OperationLog).filter(OperationLog.action == "regenerate_ai_report").count() == 0
    db.close()
    engine.dispose()


def test_regenerate_endpoint_schedules_isolated_background_task(monkeypatch):
    class SimpleUser:
        id = 9

    started_at = datetime(2026, 8, 28, 10, 0, 0)
    result = lead_service.ReportRegenerationResult(
        "started",
        "仅重新生成内容",
        7,
        9,
        "generated",
        started_at,
    )
    monkeypatch.setattr(lead_service, "trigger_report_regeneration", lambda *_args: result)
    background = BackgroundTasks()
    response = leads_endpoint.regenerate_lead_ai_report(1, background, object(), SimpleUser())
    assert response == {"status": "started", "message": "仅重新生成内容"}
    assert len(background.tasks) == 1
    task = background.tasks[0]
    assert task.func is lead_service.run_report_regeneration_task
    assert task.args == (7, 9, "generated", started_at)


def test_regenerate_endpoint_uses_real_admin_only_guard_and_maps_conflict(monkeypatch):
    route = next(
        item
        for item in leads_endpoint.router.routes
        if getattr(item, "path", "") == "/api/admin/leads/{lead_id}/regenerate-report"
    )
    assert any(dependency.call is AdminOnly for dependency in route.dependant.dependencies)

    def conflict(*_args):
        raise lead_service.LeadConflictError("正在处理")

    monkeypatch.setattr(lead_service, "trigger_report_regeneration", conflict)
    with pytest.raises(HTTPException) as raised:
        leads_endpoint.regenerate_lead_ai_report(1, BackgroundTasks(), object(), object())
    assert raised.value.status_code == 409
    assert raised.value.detail == "正在处理"

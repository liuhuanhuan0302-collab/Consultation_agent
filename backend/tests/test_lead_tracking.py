"""线索三维状态（查看/处理/导出）、列表筛选、批量导出批次与提示相关测试。"""

import csv
import io
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    CompanyLead,
    DiagnosisSubmission,
    ExportBatch,
    ExportBatchLead,
    ExportLog,
    OperationLog,
    Report,
    ReportDeliveryJob,
    Role,
    User,
)
from app.service import lead_service
from app.service.lead_status import sync_lead_processing_status
from app.utils.time_utils import utc_now


def create_db() -> tuple[Session, object, User]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    db.add(user)
    db.commit()
    return db, engine, user


def _lead_with_pipeline(
    db: Session,
    *,
    company_name: str = "Example",
    view_status: str = "unviewed",
    processing_status: str = "pending",
    processing_note: str | None = None,
    export_status: str = "unexported",
    industry: str | None = "制造业",
    lead_level: str = "low",
    report_status: str | None = None,
    research_status: str | None = None,
    generation_error: str | None = None,
    delivery_status: str | None = None,
    delivery_error: str | None = None,
    email: str = "customer@example.com",
) -> CompanyLead:
    lead = CompanyLead(
        company_name=company_name,
        industry=industry,
        lead_level=lead_level,
        email=email,
        view_status=view_status,
        processing_status=processing_status,
        processing_note=processing_note,
        export_status=export_status,
    )
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(
        submission_id=submission.id,
        title="R",
        html_content="",
        status=report_status or "pending",
        research_status=research_status or "pending",
        generation_error=generation_error,
    )
    db.add(report)
    db.flush()
    if delivery_status:
        db.add(
            ReportDeliveryJob(
                lead_id=lead.id,
                submission_id=submission.id,
                report_id=report.id,
                recipient_email=email,
                status=delivery_status,
                last_error=delivery_error,
                attempts=3,
                max_attempts=3,
            )
        )
    db.commit()
    return lead


# ── 新线索默认状态 ──────────────────────────────────────────────────


def test_new_lead_defaults_to_unviewed_unexported_pending():
    db, engine, user = create_db()
    lead = CompanyLead(company_name="New")
    db.add(lead)
    db.commit()

    assert lead.view_status == "unviewed"
    assert lead.export_status == "unexported"
    assert lead.processing_status == "pending"
    assert lead.first_viewed_at is None
    assert lead.first_exported_at is None
    db.close()
    engine.dispose()


# ── 首次查看详情记录 ────────────────────────────────────────────────


def test_first_view_records_status_time_operator_and_audit_once():
    db, engine, user = create_db()
    lead = _lead_with_pipeline(db)
    lead_id = lead.id

    detail = lead_service.get_lead_detail(db, lead_id, user)

    assert detail["lead"]["view_status"] == "viewed"
    assert detail["lead"]["first_viewed_by"] == "Admin"
    assert detail["lead"]["first_viewed_at"] is not None
    first_viewed_at = lead.first_viewed_at
    assert db.query(OperationLog).filter(OperationLog.action == "view_lead").count() == 1

    # 重复打开（含轮询刷新）不更新首次查看记录
    lead_service.get_lead_detail(db, lead_id, user)
    assert lead.first_viewed_at == first_viewed_at
    assert db.query(OperationLog).filter(OperationLog.action == "view_lead").count() == 1
    db.close()
    engine.dispose()


def test_view_recording_does_not_change_export_status():
    db, engine, user = create_db()
    lead = _lead_with_pipeline(db, export_status="unexported")

    lead_service.get_lead_detail(db, lead.id, user)

    assert lead.export_status == "unexported"
    db.close()
    engine.dispose()


# ── 列表筛选组合 ────────────────────────────────────────────────────


def test_list_filters_combine_with_and_semantics():
    db, engine, user = create_db()
    old = utc_now() - timedelta(days=10)
    recent = utc_now() - timedelta(days=1)
    _lead_with_pipeline(db, company_name="Match", view_status="unviewed", processing_status="manual_review", export_status="unexported", lead_level="high")
    _lead_with_pipeline(db, company_name="Viewed", view_status="viewed", processing_status="manual_review", export_status="unexported", lead_level="high")
    _lead_with_pipeline(db, company_name="Completed", view_status="viewed", processing_status="completed", export_status="exported", lead_level="medium")
    match_lead = db.query(CompanyLead).filter(CompanyLead.company_name == "Match").one()
    match_lead.created_at = recent
    for name in ("Viewed", "Completed"):
        db.query(CompanyLead).filter(CompanyLead.company_name == name).one().created_at = old
    db.commit()

    results = lead_service.list_admin_leads(
        db,
        lead_level="high",
        view_status="unviewed",
        processing_status="manual_review",
        export_status="unexported",
        created_from=(utc_now() - timedelta(days=3)).date(),
    )

    assert [lead.company_name for lead in results] == ["Match"]

    none_results = lead_service.list_admin_leads(
        db, lead_level="high", view_status="unviewed", processing_status="completed"
    )
    assert none_results == []
    db.close()
    engine.dispose()


def test_list_sort_oldest_first():
    db, engine, user = create_db()
    lead_a = _lead_with_pipeline(db, company_name="A")
    lead_b = _lead_with_pipeline(db, company_name="B")
    lead_a.updated_at = utc_now() - timedelta(days=2)
    lead_b.updated_at = utc_now() - timedelta(days=1)
    db.commit()

    newest = lead_service.list_admin_leads(db, sort="newest")
    oldest = lead_service.list_admin_leads(db, sort="oldest")

    assert newest[0].company_name == "B"
    assert oldest[0].company_name == "A"
    db.close()
    engine.dispose()


# ── 一键导出未导出客户 ──────────────────────────────────────────────


def test_export_unexported_marks_creates_batch_and_supports_redownload():
    db, engine, user = create_db()
    manual = _lead_with_pipeline(db, company_name="Manual", processing_status="manual_review", processing_note="AI 报告生成失败：x")
    completed = _lead_with_pipeline(db, company_name="Done", processing_status="completed")
    _lead_with_pipeline(db, company_name="Already", export_status="exported")
    db.commit()

    result = lead_service.export_unexported_leads(db, user)

    assert result.rows_count == 2
    assert result.batch_id is not None
    db.expire_all()
    for name in ("Manual", "Done"):
        lead = db.query(CompanyLead).filter(CompanyLead.company_name == name).one()
        assert lead.export_status == "exported"
        assert lead.first_exported_at is not None
        assert lead.last_exported_at is not None
    # 已导出客户不受影响；未导出标记保持不变，不受本次导出影响
    assert db.query(CompanyLead).filter(CompanyLead.company_name == "Already").one().export_status == "exported"

    batch = db.query(ExportBatch).one()
    assert batch.rows_count == 2
    assert batch.user_id == user.id
    assert b"\xef\xbb\xbf" not in batch.content and "公司".encode("utf-8") in batch.content
    rows = list(csv.reader(io.StringIO(batch.content.decode("utf-8"))))
    header = rows[0]
    for column in ("查看状态", "处理状态", "处理备注", "导出状态", "首次查看时间", "首次导出时间", "最近导出时间"):
        assert column in header
    company_index = header.index("公司")
    assert {row[company_index] for row in rows[1:]} == {"Manual", "Done"}

    detail_ids = {row.lead_id for row in db.query(ExportBatchLead).filter(ExportBatchLead.batch_id == batch.id).all()}
    assert detail_ids == {manual.id, completed.id}
    assert db.query(ExportLog).filter(ExportLog.export_type == "leads_unexported_batch").count() == 1

    batches = lead_service.list_export_batches(db)
    assert len(batches) == 1
    assert batches[0].rows_count == 2
    assert batches[0].exported_by == "Admin"
    assert batches[0].filters_summary == "一键导出未导出客户"

    download = lead_service.download_export_batch(db, batch.id)
    assert download.content == batch.content
    assert download.filename == batch.file_name
    db.close()
    engine.dispose()


def test_export_unexported_skips_empty_names_and_second_run_is_empty():
    db, engine, user = create_db()
    _lead_with_pipeline(db, company_name="Real")
    db.add(CompanyLead(company_name=None))
    db.commit()

    first = lead_service.export_unexported_leads(db, user)
    second = lead_service.export_unexported_leads(db, user)

    assert first.rows_count == 1
    assert second.rows_count == 0
    assert second.batch_id is None
    assert "没有未导出" in second.message
    assert db.query(ExportBatch).count() == 1
    # 会话占位行（无公司名）不被导出、不被标记
    placeholder = db.query(CompanyLead).filter(CompanyLead.company_name.is_(None)).one()
    assert placeholder.export_status == "unexported"
    db.close()
    engine.dispose()


def test_export_unexported_endpoint_returns_batch_payload():
    db, engine, user = create_db()
    _lead_with_pipeline(db, company_name="Real")
    from app.api.v1.endpoints.admin import leads as leads_endpoint

    payload = leads_endpoint.export_unexported_leads(db, SimpleUser())

    assert payload["rows_count"] == 1
    assert payload["batch_id"] is not None
    assert "已导出" in payload["message"]
    db.close()
    engine.dispose()


class SimpleUser:
    id = 1


# ── 导出筛选结果不标记不建批次 ───────────────────────────────────────


def test_export_filtered_does_not_mark_or_batch():
    db, engine, user = create_db()
    _lead_with_pipeline(db, company_name="In", processing_status="manual_review")
    _lead_with_pipeline(db, company_name="Out", processing_status="completed")
    db.commit()

    content = lead_service.export_leads_csv(db, user, processing_status="manual_review")

    rows = list(csv.reader(io.StringIO(content)))
    company_index = rows[0].index("公司")
    assert [row[company_index] for row in rows[1:]] == ["In"]
    for name in ("In", "Out"):
        assert db.query(CompanyLead).filter(CompanyLead.company_name == name).one().export_status == "unexported"
    assert db.query(ExportBatch).count() == 0
    log = db.query(ExportLog).filter(ExportLog.export_type == "leads").one()
    assert log.rows_count == 1
    assert "processing_status" in (log.filters_json or "")
    db.close()
    engine.dispose()


# ── 处理状态推导与同步 ──────────────────────────────────────────────


def test_sync_processing_status_derives_from_pipeline():
    cases = [
        ({"report_status": "generated", "delivery_status": "sent"}, "completed", None),
        ({"report_status": "pending", "delivery_status": "queued"}, "processing", None),
        ({"report_status": "pending", "delivery_status": "processing"}, "processing", None),
        ({"report_status": "failed", "generation_error": "生成炸了"}, "manual_review", "AI 报告生成失败：生成炸了"),
        ({"report_status": "pending", "research_status": "failed", "generation_error": "检索炸了"}, "manual_review", "企业情报检索失败：检索炸了"),
        ({"report_status": "generated", "delivery_status": "failed", "delivery_error": "SMTP 挂了"}, "manual_review", "邮件/PDF 投递失败：SMTP 挂了"),
        ({"report_status": "generated"}, "manual_review", "报告已生成，未创建投递任务（可能缺少诊断邮箱）"),
    ]
    for pipeline, expected_status, expected_note in cases:
        db, engine, user = create_db()
        lead = _lead_with_pipeline(db, **pipeline)

        sync_lead_processing_status(db, lead.id)
        db.commit()
        db.refresh(lead)

        assert lead.processing_status == expected_status, pipeline
        assert lead.processing_note == expected_note, pipeline
        db.close()
        engine.dispose()


def test_sync_processing_status_without_submission_stays_pending():
    db, engine, user = create_db()
    lead = CompanyLead(company_name="Bare", processing_status="completed")
    db.add(lead)
    db.commit()

    sync_lead_processing_status(db, lead.id)
    db.commit()
    db.refresh(lead)

    assert lead.processing_status == "pending"
    assert lead.processing_note is None
    db.close()
    engine.dispose()


def test_trigger_research_and_resume_move_lead_to_processing(monkeypatch):
    db, engine, user = create_db()
    lead = _lead_with_pipeline(
        db,
        report_status="failed",
        research_status="generated",
        generation_error="旧错误",
    )
    report = db.query(Report).filter(Report.submission_id == lead.submissions[0].id).one()
    report.company_research_json = '{"ok": true}'
    db.commit()
    monkeypatch.setattr(lead_service, "effective_search_config", lambda _db: object())

    lead_service.trigger_research(db, user, lead.id, force=True)
    db.refresh(lead)
    assert lead.processing_status == "processing"

    lead_service.resume_report_delivery(db, user, lead.id)
    db.refresh(lead)
    assert lead.processing_status == "processing"
    db.close()
    engine.dispose()


# ── 删除线索与批次明细 ──────────────────────────────────────────────


def test_delete_lead_removes_batch_details_but_keeps_snapshot():
    db, engine, user = create_db()
    lead = _lead_with_pipeline(db, company_name="Doomed", export_status="exported")
    batch = ExportBatch(user_id=user.id, rows_count=1, file_name="old.csv", content=b"csv")
    db.add(batch)
    db.flush()
    db.add(ExportBatchLead(batch_id=batch.id, lead_id=lead.id))
    db.commit()

    lead_service.delete_lead(db, user, lead.id)

    assert db.query(ExportBatchLead).filter(ExportBatchLead.lead_id == lead.id).count() == 0
    kept = db.query(ExportBatch).one()
    assert kept.content == b"csv"
    download = lead_service.download_export_batch(db, kept.id)
    assert download.content == b"csv"
    db.close()
    engine.dispose()

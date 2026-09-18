"""Regression coverage for historical/incomplete admin lead detail rows."""

import json

from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CompanyLead, DiagnosisSubmission, DimensionScore, Report, ReportDeliveryJob
from app.schemas import LeadResponse
from app.service import lead_service


def _db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def _lead(db: Session, *, report: bool = True, delivery: bool = False) -> CompanyLead:
    lead = CompanyLead(company_name="Compatibility customer", email="customer@example.com")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id, status="submitted")
    db.add(submission)
    db.flush()
    report_row = None
    if report:
        report_row = Report(
            submission_id=submission.id,
            title="诊断报告",
            html_content="<article><h2>一、执行摘要</h2></article>",
            summary_json="{}",
        )
        db.add(report_row)
        db.flush()
    if delivery and report_row:
        db.add(
            ReportDeliveryJob(
                lead_id=lead.id,
                submission_id=submission.id,
                report_id=report_row.id,
                recipient_email=lead.email,
                status="queued",
                # Explicitly null is valid for legacy rows before queue placement.
                queue_state=None,
                processing_stage=None,
            )
        )
    db.commit()
    return lead


def test_complete_report_detail_is_json_serializable_and_schema_valid() -> None:
    db, engine = _db()
    lead = _lead(db, report=True, delivery=True)

    detail = lead_service.get_lead_detail(db, lead.id)

    LeadResponse.model_validate(detail["lead"])
    jsonable_encoder(detail)
    assert detail["report"]["id"] is not None
    assert detail["delivery"]["queue_state"] is None
    db.close()
    engine.dispose()


def test_missing_report_returns_200_shaped_detail() -> None:
    db, engine = _db()
    lead = _lead(db, report=False)

    detail = lead_service.get_lead_detail(db, lead.id)

    assert detail["report"] is None
    assert detail["delivery"] is None
    assert detail["queue_task"] is None
    jsonable_encoder(detail)
    db.close()
    engine.dispose()


def test_submission_without_delivery_returns_200_shaped_detail() -> None:
    db, engine = _db()
    lead = _lead(db, report=True, delivery=False)

    detail = lead_service.get_lead_detail(db, lead.id)

    assert detail["submission"]["id"] is not None
    assert detail["report"]["id"] is not None
    assert detail["delivery"] is None
    assert detail["queue_task"] is None
    db.close()
    engine.dispose()


def test_historical_null_queue_fields_and_orphan_dimension_are_safe() -> None:
    db, engine = _db()
    lead = _lead(db, report=True, delivery=False)
    submission = db.query(DiagnosisSubmission).filter_by(lead_id=lead.id).one()
    db.add(
        DimensionScore(
            submission_id=submission.id,
            module_id=999,
            raw_score=0,
            max_score=4,
            score_rate=0,
            risk_level="low",
        )
    )
    report = submission.report
    report.summary_json = "{malformed"
    report.company_research_json = "{malformed"
    db.commit()

    detail = lead_service.get_lead_detail(db, lead.id)

    assert detail["report"]["summary"] == {}
    assert detail["report"]["company_research"] is None
    assert detail["submission"]["dimensions"][0]["module_code"] is None
    jsonable_encoder(detail)
    db.close()
    engine.dispose()

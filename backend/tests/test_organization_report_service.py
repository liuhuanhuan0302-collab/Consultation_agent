import asyncio
import json

from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import MEDIUMTEXT, dialect as mysql_dialect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.service.organization_report_service as organization_report_service
from app.database import Base
from app.models import (
    CompanyLead,
    DiagnosisSubmission,
    OrganizationAnalysisStatus,
    OrganizationReport,
    OrganizationReportTask,
    OrganizationReportStatus,
    OrganizationReportTaskStatus,
    OrganizationSubmission,
    OrganizationSubmissionStatus,
    Question,
    QuestionModule,
    Report,
    ReportStatus,
    SubmissionStatus,
)
from app.repositories.organization_repo import upsert_answers
from app.repositories.organization_report_repo import claim_next_task
from app.utils.time_utils import utc_now


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def _fixture(db: Session):
    module = QuestionModule(code="M01", name="一心", max_score=8, sort_order=1)
    db.add(module)
    db.flush()
    questions = [
        Question(module_id=module.id, code="Q01", dimension="用户洞察", text="是否建立用户洞察机制？", sort_order=1),
        Question(module_id=module.id, code="Q02", dimension="决策速度", text="流程以用户为原点吗？", sort_order=2),
    ]
    db.add_all(questions)
    lead = CompanyLead(company_name="示例企业有限公司", industry="软件服务", city="广州")
    enterprise_submission = DiagnosisSubmission(lead=lead, status=SubmissionStatus.submitted.value)
    db.add(enterprise_submission)
    db.flush()
    enterprise_report = Report(
        submission_id=enterprise_submission.id,
        status=ReportStatus.generated.value,
        title="示例企业企业诊断报告",
        html_content="<p>企业诊断</p>",
        company_research_json=json.dumps({"company_overview": "已核验的企业信息"}, ensure_ascii=False),
        research_status="generated",
    )
    db.add(enterprise_report)
    submission = OrganizationSubmission(
        company_name_input="示例企业",
        company_name="示例企业有限公司",
        respondent_name="张三",
        department="产品部",
        position="部门负责人",
        status=OrganizationSubmissionStatus.submitted.value,
        submitted_at=utc_now(),
    )
    db.add(submission)
    db.flush()
    upsert_answers(db, submission.id, [(questions[0].id, 1), (questions[1].id, 4)])
    db.commit()
    return lead, enterprise_report, submission, questions


def test_organization_report_html_uses_mediumtext_on_mysql():
    html_type = OrganizationReport.__table__.c.html_content.type

    assert isinstance(html_type.dialect_impl(mysql_dialect()), MEDIUMTEXT)


def _analysis_for(payload):
    return {
        "modules": [
            {
                "module_code": module["module_code"],
                "core_diagnosis": f"{module['module_name']}存在需要关注的部门信号。",
                "root_cause": "部门机制仍需要结合内部资料进一步核验。",
                "question_interpretations": [
                    {
                        "question_code": question["question_code"],
                        "signal": f"{question['question_code']}的当前得分反映出部门现状。",
                    }
                    for question in module["questions"]
                ],
            }
            for module in payload.data["modules"]
        ],
        "overall_core_diagnosis": ["部门在部分能力项上存在差异。", "建议优先核验低分题对应机制。"],
        "overall_root_cause": "当前结论来自答卷与规则评分，深层原因需要内部资料验证。",
        "recommendations": ["围绕低分题补充具体流程证据。", "在部门例会上确认改进责任。"],
    }


def test_auto_analysis_requires_valid_enterprise_report_and_queues_independent_task(monkeypatch):
    engine, db = _db()
    try:
        lead, enterprise_report, submission, _questions = _fixture(db)
        monkeypatch.setattr(organization_report_service, "validate_structured_research", lambda _value: [])

        organization_report_service.prepare_auto_analysis(db, submission.id)

        db.expire_all()
        stored_submission = db.get(OrganizationSubmission, submission.id)
        assert stored_submission.analysis_status == OrganizationAnalysisStatus.queued.value
        assert db.query(OrganizationReport).count() == 1
        assert db.query(OrganizationReport).one().source_enterprise_report_id == enterprise_report.id
        assert db.query(OrganizationReport).one().version == 1
        assert db.query(OrganizationReport).one().status == OrganizationReportStatus.pending.value
        assert db.query(OrganizationReport).one().organization_submission_id == submission.id
        assert db.query(Report).count() == 1
        assert db.query(CompanyLead).count() == 1
        assert lead.company_name == "示例企业有限公司"
    finally:
        db.close()
        engine.dispose()


def test_second_same_department_submission_waits_for_manual_decision(monkeypatch):
    engine, db = _db()
    try:
        monkeypatch.setattr(organization_report_service, "validate_structured_research", lambda _value: [])
        _lead, _enterprise_report, first, _questions = _fixture(db)
        second = OrganizationSubmission(
            company_name_input="示例企业",
            company_name="示例企业有限公司",
            respondent_name="李四",
            department=first.department,
            position="负责人",
            status=OrganizationSubmissionStatus.submitted.value,
            submitted_at=utc_now(),
        )
        db.add(second)
        db.commit()

        organization_report_service.prepare_auto_analysis(db, second.id)

        db.expire_all()
        stored = db.get(OrganizationSubmission, second.id)
        assert stored.analysis_status == OrganizationAnalysisStatus.waiting_manual.value
        assert db.query(OrganizationReport).count() == 0
        assert "人工" in (stored.analysis_note or "")
    finally:
        db.close()
        engine.dispose()


def test_current_payload_uses_live_questions_and_persists_no_question_text_snapshot(monkeypatch):
    engine, db = _db()
    try:
        monkeypatch.setattr(organization_report_service, "validate_structured_research", lambda _value: [])
        _lead, _enterprise_report, submission, questions = _fixture(db)
        payload = organization_report_service.build_current_payload(db, submission)

        assert payload.enterprise_report_id == _enterprise_report.id
        assert len(payload.data["modules"]) == 1
        assert len(payload.data["modules"][0]["questions"]) == len(questions)
        assert payload.data["score"]["average_out_of_4"] == 2.5
        assert payload.data["modules"][0]["questions"][0]["short_title"] == "用户洞察"
        stored = organization_report_service._stored_summary(payload)
        assert "question_text" not in json.dumps(stored, ensure_ascii=False)
        assert stored["modules"][0]["questions"][0]["answer_value"] == 1
    finally:
        db.close()
        engine.dispose()


def test_report_task_generates_pdf_and_does_not_touch_enterprise_chain(monkeypatch):
    engine, db = _db()
    try:
        monkeypatch.setattr(organization_report_service, "validate_structured_research", lambda _value: [])
        _lead, _enterprise_report, submission, _questions = _fixture(db)
        organization_report_service.prepare_auto_analysis(db, submission.id)
        claimed = claim_next_task(db, utc_now())
        assert claimed is not None
        task_id, lock_token = claimed

        async def fake_llm(_db, payload, validation_feedback=None):
            return json.dumps(_analysis_for(payload), ensure_ascii=False), "test-model"

        monkeypatch.setattr(organization_report_service, "call_organization_llm", fake_llm)
        monkeypatch.setattr(organization_report_service, "render_report_pdf_bytes_with_browser_html", lambda _html: b"%PDF-test")
        monkeypatch.setattr(organization_report_service, "_validate_pdf", lambda _content: None)
        monkeypatch.setattr(organization_report_service, "SessionLocal", lambda: Session(engine))

        assert asyncio.run(organization_report_service.process_organization_report_task(task_id, lock_token)) is True

        db.expire_all()
        report = db.query(OrganizationReport).one()
        task = db.query(OrganizationReportTask).one()
        assert report.status == OrganizationReportStatus.generated.value
        assert report.pdf_content == b"%PDF-test"
        assert task.status == OrganizationReportTaskStatus.succeeded.value
        assert json.loads(report.analysis_json)["modules"][0]["module_code"] == "M01"
        assert db.query(Report).count() == 1
        assert db.query(CompanyLead).count() == 1
        assert db.query(DiagnosisSubmission).count() == 1
        stored = db.get(OrganizationSubmission, submission.id)
        assert stored.analysis_status == OrganizationAnalysisStatus.generated.value
    finally:
        db.close()
        engine.dispose()

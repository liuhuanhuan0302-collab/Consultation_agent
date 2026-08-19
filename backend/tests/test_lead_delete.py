"""线索删除级联清理测试 — 删除 lead 后所有关联数据一并删除。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    AiConversationMessage,
    CompanyLead,
    DiagnosisSubmission,
    DimensionScore,
    Question,
    QuestionAnswer,
    QuestionModule,
    Recommendation,
    Report,
    ReportDeliveryJob,
    Role,
    TrackingEvent,
    User,
)
from app.repositories.consult_repo import delete_lead_cascade


def test_delete_lead_cascade_removes_all_related_rows():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)

    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    lead = CompanyLead(company_name="待删除公司", session_token="sess123")
    db.add_all([user, lead])
    db.flush()

    module = QuestionModule(code="M01", name="一心", max_score=28, sort_order=1)
    db.add(module)
    db.flush()
    question = Question(module_id=module.id, code="Q1", text="测试题", max_score=4, sort_order=1)
    db.add(question)
    db.flush()

    submission = DiagnosisSubmission(lead_id=lead.id, status="submitted", total_score=10, max_score=28)
    db.add(submission)
    db.flush()

    db.add_all(
        [
            QuestionAnswer(submission_id=submission.id, question_id=question.id, score=2),
            DimensionScore(submission_id=submission.id, module_id=module.id, raw_score=10, max_score=28, score_rate=0.357, risk_level="较弱"),
        ]
    )

    report = Report(
        submission_id=submission.id,
        title="测试报告",
        html_content="<article></article>",
        status="generated",
    )
    db.add(report)
    db.flush()

    db.add_all(
        [
            Recommendation(report_id=report.id, reason="匹配", priority_score=80),
            AiConversationMessage(lead_id=lead.id, submission_id=submission.id, report_id=report.id, role="user", content="prompt"),
            ReportDeliveryJob(lead_id=lead.id, submission_id=submission.id, report_id=report.id, recipient_email="a@b.com", status="sent"),
            TrackingEvent(session_token="sess123", lead_id=lead.id, event_name="submit_questionnaire"),
        ]
    )
    db.commit()

    lead_id, submission_id, report_id = lead.id, submission.id, report.id

    delete_lead_cascade(db, lead)
    db.commit()

    assert db.query(CompanyLead).filter(CompanyLead.id == lead_id).first() is None
    assert db.query(DiagnosisSubmission).filter(DiagnosisSubmission.id == submission_id).first() is None
    assert db.query(Report).filter(Report.id == report_id).first() is None
    assert db.query(QuestionAnswer).filter(QuestionAnswer.submission_id == submission_id).count() == 0
    assert db.query(DimensionScore).filter(DimensionScore.submission_id == submission_id).count() == 0
    assert db.query(Recommendation).filter(Recommendation.report_id == report_id).count() == 0
    assert db.query(AiConversationMessage).filter(AiConversationMessage.report_id == report_id).count() == 0
    assert db.query(AiConversationMessage).filter(AiConversationMessage.lead_id == lead_id).count() == 0
    assert db.query(ReportDeliveryJob).filter(ReportDeliveryJob.lead_id == lead_id).count() == 0
    assert db.query(TrackingEvent).filter(TrackingEvent.lead_id == lead_id).count() == 0
    # 题库本身不受影响
    assert db.query(QuestionModule).filter(QuestionModule.id == module.id).first() is not None
    assert db.query(Question).filter(Question.id == question.id).first() is not None

    db.close()
    engine.dispose()

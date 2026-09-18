from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import OrganizationAnswer, OrganizationSubmission
from app.repositories.organization_repo import (
    create_submission,
    get_submission,
    get_submission_for_update,
    list_answers,
    upsert_answers,
)
from app.schemas.organization import (
    OrganizationAnswerBatch,
    OrganizationSubmissionCreate,
)


def create_db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def test_organization_tables_are_standalone_and_answers_are_unique():
    db, engine = create_db()

    submission = create_submission(
        db,
        company_name_input="奥飞",
        company_name="奥飞娱乐股份有限公司",
        respondent_name="王小明",
        department="产品部",
        position="负责人",
    )
    upsert_answers(db, submission.id, [(1, 2), (2, 4)])
    db.commit()

    assert get_submission(db, submission.id).company_name == "奥飞娱乐股份有限公司"
    assert get_submission_for_update(db, submission.id).id == submission.id
    assert [(answer.question_id, answer.answer_value) for answer in list_answers(db, submission.id)] == [
        (1, 2),
        (2, 4),
    ]

    duplicate = OrganizationAnswer(
        organization_submission_id=submission.id,
        question_id=1,
        answer_value=3,
    )
    db.add(duplicate)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError("organization answers must be unique per submission and question")

    submission_columns = set(inspect(OrganizationSubmission).columns.keys())
    assert submission_columns == {
        "id",
        "access_token",
        "company_name_input",
        "company_name",
        "respondent_name",
        "department",
        "position",
        "status",
        "analysis_status",
        "analysis_note",
        "created_at",
        "submitted_at",
    }
    assert not {
        "company_lead_id",
        "contact_name",
        "phone",
        "email",
    } & submission_columns
    assert not OrganizationSubmission.__table__.foreign_keys

    answer_foreign_keys = {
        foreign_key.target_fullname for foreign_key in OrganizationAnswer.__table__.foreign_keys
    }
    assert answer_foreign_keys == {
        "organization_submissions.id",
        "questions.id",
    }
    db.close()
    engine.dispose()


def test_organization_repository_updates_existing_raw_answer_without_duplicates():
    db, engine = create_db()
    submission = create_submission(
        db,
        company_name_input="测试企业",
        company_name="测试企业",
        respondent_name="测试姓名",
        department="研发部",
        position="经理",
    )
    upsert_answers(db, submission.id, [(10, 1)])
    db.commit()
    original = list_answers(db, submission.id)[0]
    original_created_at = original.created_at
    original_id = original.id

    upsert_answers(db, submission.id, [(10, 4), (11, 0)])
    db.commit()

    answers = list_answers(db, submission.id)
    assert [(answer.id, answer.question_id, answer.answer_value) for answer in answers] == [
        (original_id, 10, 4),
        (answers[1].id, 11, 0),
    ]
    assert answers[0].created_at == original_created_at
    db.close()
    engine.dispose()


def test_organization_schemas_match_minimal_phase_two_contract():
    submission = OrganizationSubmissionCreate(
        company_name_input="奥飞",
        company_name="奥飞娱乐股份有限公司",
        respondent_name="王小明",
        department="产品部",
        position="负责人",
    )
    answers = OrganizationAnswerBatch(answers=[{"question_id": 1, "answer_value": 4}])

    assert submission.model_dump() == {
        "company_name_input": "奥飞",
        "company_name": "奥飞娱乐股份有限公司",
        "respondent_name": "王小明",
        "department": "产品部",
        "position": "负责人",
    }
    assert answers.answers[0].answer_value == 4

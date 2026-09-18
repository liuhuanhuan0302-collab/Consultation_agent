import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.service.company_research as company_research
import app.service.email_service as email_service
import app.service.pdf_service as pdf_service
import app.service.report_queue as report_queue
import app.service.reporting as reporting
from app.api.v1.endpoints import organization
from app.database import Base, get_db
from app.models import (
    CompanyLead,
    DiagnosisSubmission,
    OrganizationAnswer,
    OrganizationSubmission,
    Question,
    QuestionAnswer,
    QuestionModule,
    Report,
    ReportDeliveryJob,
)


@pytest.fixture
def organization_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with Session(engine) as db:
        module = QuestionModule(code="M01", name="组织诊断", max_score=272, sort_order=1)
        db.add(module)
        db.flush()
        db.add_all(
            [
                Question(
                    module_id=module.id,
                    code=f"Q{index:02d}",
                    text=f"问题 {index}",
                    sort_order=index,
                )
                for index in range(1, 69)
            ]
        )
        db.add_all(
            [
                CompanyLead(
                    company_name="奥飞娱乐股份有限公司",
                    contact_name="不应返回",
                    phone="13800000000",
                    email="private@example.com",
                    annual_revenue="不应返回",
                ),
                CompanyLead(company_name="奥飞娱乐股份有限公司", contact_name="重复记录"),
                CompanyLead(company_name="某奥飞科技有限公司", contact_name="内部联系人"),
            ]
        )
        db.commit()

    app = FastAPI()
    app.state.limiter = Limiter(key_func=organization.client_ip)
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(organization.router)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    organization.limiter.reset()
    with TestClient(app) as client:
        yield client, session_factory
    organization.limiter.reset()
    engine.dispose()


def _create_submission(client: TestClient) -> tuple[int, str]:
    response = client.post(
        "/api/public/organization/submissions",
        json={
            "company_name_input": "奥飞",
            "company_name": "奥飞娱乐股份有限公司",
            "respondent_name": "王小明",
            "department": "信息技术部",
            "position": "IT经理",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["id"], data["access_token"]


def _answers(count: int = 68) -> list[dict[str, int]]:
    return [{"question_id": index, "answer_value": index % 5} for index in range(1, count + 1)]


def test_company_suggestions_are_read_only_limited_deduplicated_and_safe(organization_api):
    client, session_factory = organization_api
    with Session(session_factory.kw["bind"]) as db:
        db.add_all([CompanyLead(company_name=f"测试企业{index:02d}") for index in range(15)])
        db.commit()

    assert client.get("/api/public/organization/company-suggestions?q=").json() == {"items": []}
    assert client.get("/api/public/organization/company-suggestions?q=奥").json() == {"items": []}

    response = client.get("/api/public/organization/company-suggestions?q=%20奥飞%20")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"company_name": "奥飞娱乐股份有限公司"},
            {"company_name": "某奥飞科技有限公司"},
        ]
    }
    assert all(set(item) == {"company_name"} for item in response.json()["items"])

    limited = client.get("/api/public/organization/company-suggestions?q=测试")
    assert limited.status_code == 200
    assert len(limited.json()["items"]) == 10
    assert all(item["company_name"].startswith("测试企业") for item in limited.json()["items"])

    assert client.get("/api/public/organization/company-suggestions?q=不存在").json() == {"items": []}
    special = client.get("/api/public/organization/company-suggestions?q=%25_%25")
    assert special.status_code == 200
    assert special.json() == {"items": []}


def test_company_suggestions_enforce_the_configured_rate_limit(organization_api):
    client, _ = organization_api

    responses = [
        client.get("/api/public/organization/company-suggestions?q=奥飞")
        for _ in range(120)
    ]
    assert [response.status_code for response in responses] == [200] * 120

    exceeded = client.get("/api/public/organization/company-suggestions?q=奥飞")
    assert exceeded.status_code == 429


def test_organization_create_validates_required_fields_and_allows_unknown_company(organization_api):
    client, session_factory = organization_api
    for field in ("company_name", "respondent_name", "department", "position"):
        payload = {
            "company_name_input": "未知企业",
            "company_name": "未知企业",
            "respondent_name": "王小明",
            "department": "研发部",
            "position": "研发经理",
        }
        payload[field] = ""
        assert client.post("/api/public/organization/submissions", json=payload).status_code == 422

    before_leads = 0
    with Session(session_factory.kw["bind"]) as db:
        before_leads = db.query(CompanyLead).count()

    response = client.post(
        "/api/public/organization/submissions",
        json={
            "company_name_input": "某某未来科技有限公司",
            "company_name": "某某未来科技有限公司",
            "respondent_name": " 王小明 ",
            "department": " 研发部 ",
            "position": "研发经理",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert len(response.json()["access_token"]) == 32

    with Session(session_factory.kw["bind"]) as db:
        assert db.query(CompanyLead).count() == before_leads
        saved = db.get(OrganizationSubmission, response.json()["id"])
        assert saved.company_name == "某某未来科技有限公司"
        assert saved.respondent_name == "王小明"
        assert saved.department == "研发部"


def test_organization_answers_use_token_and_atomic_upsert(organization_api):
    client, session_factory = organization_api
    submission_id, access_token = _create_submission(client)
    headers = {"X-Organization-Access-Token": access_token}

    saved = client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers=headers,
        json={"answers": [{"question_id": 1, "answer_value": 2}]},
    )
    assert saved.status_code == 200
    updated = client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers=headers,
        json={"answers": [{"question_id": 1, "answer_value": 4}]},
    )
    assert updated.status_code == 200

    with Session(session_factory.kw["bind"]) as db:
        answers = db.query(OrganizationAnswer).filter_by(organization_submission_id=submission_id).all()
        assert len(answers) == 1
        assert answers[0].answer_value == 4

    assert client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers={"X-Organization-Access-Token": "wrong-token-0000000000000000"},
        json={"answers": [{"question_id": 2, "answer_value": 1}]},
    ).status_code == 404
    assert client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers=headers,
        json={"answers": [{"question_id": 999, "answer_value": 1}]},
    ).status_code == 422
    assert client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers=headers,
        json={"answers": [{"question_id": 2, "answer_value": 5}]},
    ).status_code == 422
    assert client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers=headers,
        json={"answers": [{"question_id": 2, "answer_value": 1}, {"question_id": 2, "answer_value": 2}]},
    ).status_code == 422


def test_organization_submit_requires_all_active_questions(organization_api):
    client, session_factory = organization_api
    submission_id, access_token = _create_submission(client)
    response = client.post(
        f"/api/public/organization/submissions/{submission_id}/submit",
        headers={"X-Organization-Access-Token": access_token},
        json={"answers": _answers(67)},
    )
    assert response.status_code == 422
    assert "缺少题目答案" in response.json()["detail"]
    with Session(session_factory.kw["bind"]) as db:
        submission = db.get(OrganizationSubmission, submission_id)
        assert submission.status == "draft"
        assert db.query(OrganizationAnswer).filter_by(organization_submission_id=submission_id).count() == 0


def test_organization_submit_can_finalize_saved_answers_without_request_body(organization_api):
    client, session_factory = organization_api
    submission_id, access_token = _create_submission(client)
    headers = {"X-Organization-Access-Token": access_token}
    saved = client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers=headers,
        json={"answers": _answers()},
    )
    assert saved.status_code == 200

    response = client.post(
        f"/api/public/organization/submissions/{submission_id}/submit",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "submitted"
    with Session(session_factory.kw["bind"]) as db:
        assert db.query(OrganizationAnswer).filter_by(organization_submission_id=submission_id).count() == 68


def test_organization_submit_has_zero_enterprise_side_effects_and_locks_submission(
    organization_api,
    monkeypatch,
):
    client, session_factory = organization_api
    with Session(session_factory.kw["bind"]) as db:
        before = {
            "company_leads": db.query(CompanyLead).count(),
            "diagnosis_submissions": db.query(DiagnosisSubmission).count(),
            "question_answers": db.query(QuestionAnswer).count(),
            "reports": db.query(Report).count(),
            "report_delivery_jobs": db.query(ReportDeliveryJob).count(),
            "organization_submissions": db.query(OrganizationSubmission).count(),
            "organization_answers": db.query(OrganizationAnswer).count(),
        }
    submission_id, access_token = _create_submission(client)
    headers = {"X-Organization-Access-Token": access_token}

    def fail_if_called(*args, **kwargs):
        raise AssertionError("enterprise report pipeline must not run for organization submission")

    monkeypatch.setattr(report_queue, "enqueue_report_delivery", fail_if_called)
    monkeypatch.setattr(company_research, "research_company", fail_if_called)
    monkeypatch.setattr(reporting, "generate_report_content", fail_if_called)
    monkeypatch.setattr(pdf_service, "render_report_pdf_bytes", fail_if_called)
    monkeypatch.setattr(email_service, "send_report_pdf_email", fail_if_called)

    response = client.post(
        f"/api/public/organization/submissions/{submission_id}/submit",
        headers=headers,
        json={"answers": _answers()},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "submitted"
    assert response.json()["submitted_at"] is not None

    with Session(session_factory.kw["bind"]) as db:
        after = {
            "company_leads": db.query(CompanyLead).count(),
            "diagnosis_submissions": db.query(DiagnosisSubmission).count(),
            "question_answers": db.query(QuestionAnswer).count(),
            "reports": db.query(Report).count(),
            "report_delivery_jobs": db.query(ReportDeliveryJob).count(),
            "organization_submissions": db.query(OrganizationSubmission).count(),
            "organization_answers": db.query(OrganizationAnswer).count(),
        }
    assert after["company_leads"] == before["company_leads"]
    assert after["diagnosis_submissions"] == before["diagnosis_submissions"]
    assert after["question_answers"] == before["question_answers"]
    assert after["reports"] == before["reports"]
    assert after["report_delivery_jobs"] == before["report_delivery_jobs"]
    assert after["organization_submissions"] == before["organization_submissions"] + 1
    assert after["organization_answers"] == before["organization_answers"] + 68

    repeated = client.post(
        f"/api/public/organization/submissions/{submission_id}/submit",
        headers=headers,
        json={"answers": _answers()},
    )
    assert repeated.status_code == 409
    edited_after_submit = client.put(
        f"/api/public/organization/submissions/{submission_id}/answers",
        headers=headers,
        json={"answers": [{"question_id": 1, "answer_value": 0}]},
    )
    assert edited_after_submit.status_code == 409

import csv
import io
from datetime import datetime
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import admin
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
    Role,
    User,
)
from app.utils.security import create_access_token


@pytest.fixture
def organization_admin_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with Session(engine) as db:
        admin_user = User(
            email="organization-admin@example.com",
            name="组织管理员",
            role=Role.admin.value,
            password_hash="hash",
        )
        operator = User(
            email="organization-operator@example.com",
            name="运营",
            role=Role.operator.value,
            password_hash="hash",
        )
        db.add_all([admin_user, operator])
        db.flush()

        modules = [
            QuestionModule(code=f"M{index:02d}", name=f"模块 {index}", max_score=68, sort_order=index)
            for index in range(1, 5)
        ]
        db.add_all(modules)
        db.flush()
        questions = []
        for index in range(1, 69):
            module = modules[(index - 1) // 17]
            questions.append(
                Question(
                    module_id=module.id,
                    code=f"Q{index:02d}",
                    text=f"正式题目 {index}",
                    sort_order=(index - 1) % 17 + 1,
                    max_score=4,
                )
            )
        db.add_all(questions)
        db.flush()

        lead = CompanyLead(company_name="不应被组织后台读取或修改")
        db.add(lead)
        db.flush()
        enterprise_submission = DiagnosisSubmission(lead_id=lead.id)
        db.add(enterprise_submission)
        db.flush()
        db.add(Report(submission_id=enterprise_submission.id, title="企业报告", html_content="<p>report</p>"))
        db.add(QuestionAnswer(submission_id=enterprise_submission.id, question_id=questions[0].id, score=4))
        db.flush()
        db.add(
            ReportDeliveryJob(
                lead_id=lead.id,
                submission_id=enterprise_submission.id,
                report_id=1,
                recipient_email="enterprise@example.com",
            )
        )

        def add_org(
            company_name: str,
            respondent_name: str,
            department: str,
            position: str,
            status: str,
            created_at: datetime,
            submitted_at: datetime | None,
        ) -> OrganizationSubmission:
            submission = OrganizationSubmission(
                access_token=f"private-token-{respondent_name}",
                company_name_input=company_name,
                company_name=company_name,
                respondent_name=respondent_name,
                department=department,
                position=position,
                status=status,
                created_at=created_at,
                submitted_at=submitted_at,
            )
            db.add(submission)
            db.flush()
            if status == "submitted":
                db.add_all(
                    [
                        OrganizationAnswer(
                            organization_submission_id=submission.id,
                            question_id=question.id,
                            answer_value=index % 5,
                        )
                        for index, question in enumerate(questions, start=1)
                    ]
                )
            return submission

        add_org(
            "奥飞娱乐股份有限公司",
            "张三",
            "信息技术部",
            "IT经理",
            "submitted",
            datetime(2026, 9, 14, 2, 0),
            datetime(2026, 9, 14, 2, 30),
        )
        add_org(
            "奥飞娱乐股份有限公司",
            "李四",
            "人力资源部",
            "HRBP",
            "submitted",
            datetime(2026, 9, 13, 3, 0),
            datetime(2026, 9, 13, 3, 30),
        )
        add_org(
            "奥飞娱乐股份有限公司",
            "王五",
            "信息技术部",
            "工程师",
            "draft",
            datetime(2026, 9, 14, 4, 0),
            None,
        )
        add_org(
            "星河科技有限公司",
            "赵六",
            "研发部",
            "负责人",
            "submitted",
            datetime(2026, 9, 12, 4, 0),
            datetime(2026, 9, 12, 4, 30),
        )
        db.commit()
        user_ids = {"admin": admin_user.id, "operator": operator.id}

    test_app = FastAPI()
    test_app.include_router(admin.router)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_db
    with TestClient(test_app) as client:
        yield client, {role: create_access_token(str(user_id)) for role, user_id in user_ids.items()}, session_factory
    engine.dispose()


def test_organization_admin_requires_admin_role(organization_admin_api):
    client, tokens, _session_factory = organization_admin_api
    paths = (
        "/api/admin/organization/companies",
        "/api/admin/organization/submissions/1",
        "/api/admin/organization/export",
    )
    for path in paths:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": f"Bearer {tokens['operator']}"}).status_code == 403
    assert client.get(paths[0], headers={"Authorization": f"Bearer {tokens['admin']}"}).status_code == 200


def test_company_aggregation_search_filters_and_pagination_are_read_only(organization_admin_api):
    client, tokens, session_factory = organization_admin_api
    headers = {"Authorization": f"Bearer {tokens['admin']}"}

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

    response = client.get(f"/api/admin/organization/companies?page=1&page_size=1", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 2
    assert payload["pages"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0] == {
        "company_name": "奥飞娱乐股份有限公司",
        "submitted_count": 2,
        "draft_count": 1,
        "department_count": 2,
        "latest_submitted_at": "2026-09-14T02:30:00Z",
    }

    searched = client.get(
        "/api/admin/organization/companies?company_name=星河&has_submitted=true",
        headers=headers,
    )
    assert searched.status_code == 200
    assert [item["company_name"] for item in searched.json()["items"]] == ["星河科技有限公司"]
    date_filtered = client.get(
        "/api/admin/organization/companies?submitted_from=2026-09-14&submitted_to=2026-09-14",
        headers=headers,
    )
    assert [item["company_name"] for item in date_filtered.json()["items"]] == ["奥飞娱乐股份有限公司"]

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
    assert after == before


def test_company_detail_filters_and_single_submission_show_formal_question_order_without_token(
    organization_admin_api,
):
    client, tokens, _session_factory = organization_admin_api
    headers = {"Authorization": f"Bearer {tokens['admin']}"}
    company = quote("奥飞娱乐股份有限公司", safe="")

    detail = client.get(f"/api/admin/organization/companies/{company}/submissions", headers=headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["company_name"] == "奥飞娱乐股份有限公司"
    assert payload["departments"] == ["人力资源部", "信息技术部"]
    assert {item["respondent_name"] for item in payload["items"]} == {"张三", "李四", "王五"}
    assert "access_token" not in detail.text

    filtered = client.get(
        f"/api/admin/organization/companies/{company}/submissions"
        "?department=%E4%BF%A1%E6%81%AF%E6%8A%80%E6%9C%AF%E9%83%A8&status=submitted"
        "&respondent_name=%E5%BC%A0&submitted_from=2026-09-14&submitted_to=2026-09-14&page_size=1",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["respondent_name"] == "张三"

    submission_id = next(item["id"] for item in payload["items"] if item["respondent_name"] == "张三")
    single = client.get(f"/api/admin/organization/submissions/{submission_id}", headers=headers)
    assert single.status_code == 200, single.text
    single_payload = single.json()
    questions = [question for module in single_payload["modules"] for question in module["questions"]]
    assert [module["code"] for module in single_payload["modules"]] == ["M01", "M02", "M03", "M04"]
    assert len(questions) == 68
    assert [question["code"] for question in questions] == [f"Q{index:02d}" for index in range(1, 69)]
    assert questions[0] == {
        "code": "Q01",
        "text": "正式题目 1",
        "max_score": 4,
        "answer_value": 1,
    }
    assert "access_token" not in single.text


def test_organization_export_is_csv_and_matches_filters(organization_admin_api):
    client, tokens, _session_factory = organization_admin_api
    headers = {"Authorization": f"Bearer {tokens['admin']}"}
    company = quote("奥飞娱乐股份有限公司", safe="")
    response = client.get(
        f"/api/admin/organization/export?company_name={company}&status=submitted&department=%E4%BF%A1%E6%81%AF%E6%8A%80%E6%9C%AF%E9%83%A8",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "organization-diagnosis.csv" in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 2
    assert len(rows[0]) == 75
    assert rows[0][:7] == ["企业名称", "姓名", "部门", "职位", "状态", "创建时间", "提交时间"]
    assert rows[0][7:] == [f"Q{index:02d}" for index in range(1, 69)]
    assert rows[1][1:5] == ["张三", "信息技术部", "IT经理", "submitted"]
    assert rows[1][7:] == [str(index % 5) for index in range(1, 69)]
    assert "private-token" not in response.text

    default_export = client.get("/api/admin/organization/export", headers=headers)
    assert default_export.status_code == 200
    default_rows = list(csv.reader(io.StringIO(default_export.content.decode("utf-8-sig"))))
    assert len(default_rows) == 4
    assert all(row[4] == "submitted" for row in default_rows[1:])

    all_statuses = client.get("/api/admin/organization/export?status=all", headers=headers)
    assert all_statuses.status_code == 200
    all_rows = list(csv.reader(io.StringIO(all_statuses.content.decode("utf-8-sig"))))
    assert len(all_rows) == 5
    assert {row[4] for row in all_rows[1:]} == {"draft", "submitted"}

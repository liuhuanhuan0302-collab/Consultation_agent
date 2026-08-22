"""重新填写（新一轮诊断）的线索与答卷隔离 — 不再覆盖上一轮客户信息。"""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

import app.api.v1.endpoints.public as public
from app.database import Base
from app.models import CompanyLead, DiagnosisSubmission, SubmissionStatus
from app.schemas import LeadCreate


def create_db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def make_payload(**overrides) -> LeadCreate:
    defaults = dict(
        company_name="华为",
        city="广东省深圳市",
        industry="制造业",
        company_size="1-200人",
        annual_revenue="<1亿",
        contact_name="张三",
        position="CTO",
        phone="13800138000",
        email="test@example.com",
        wechat=None,
        ai_focus="想提升获客效率",
        privacy_accepted=True,
        contact_authorized=True,
        source_code="default",
        session_token=None,
    )
    defaults.update(overrides)
    return LeadCreate(**defaults)


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/api/public/leads",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
        }
    )


def test_reroll_after_completed_round_creates_new_lead_and_token():
    db, engine = create_db()
    first_lead = CompanyLead(company_name="奥飞娱乐")
    db.add(first_lead)
    db.flush()
    completed = DiagnosisSubmission(lead_id=first_lead.id, status=SubmissionStatus.scored.value)
    db.add(completed)
    db.commit()

    response = public.upsert_lead(
        make_payload(session_token=first_lead.session_token, company_name="华为"),
        make_request(),
        db,
    )

    # 新一轮使用全新线索与会话，旧线索保留第一轮的公司信息
    assert response.lead.id != first_lead.id
    assert response.lead.session_token != first_lead.session_token
    assert response.lead.company_name == "华为"
    db.refresh(first_lead)
    assert first_lead.company_name == "奥飞娱乐"
    # 新一轮拥有独立的草稿答卷
    assert response.submission_id != completed.id
    assert response.submission_id is not None
    db.close()
    engine.dispose()


def test_resume_draft_reuses_same_lead_and_submission():
    db, engine = create_db()
    lead = CompanyLead(company_name="奥飞娱乐")
    db.add(lead)
    db.flush()
    draft = DiagnosisSubmission(lead_id=lead.id, status=SubmissionStatus.draft.value)
    db.add(draft)
    db.commit()

    response = public.upsert_lead(
        make_payload(session_token=lead.session_token, company_name="华为"),
        make_request(),
        db,
    )

    # 上一轮还是草稿（未提交）：视为续答，复用同一线索与答卷
    assert response.lead.id == lead.id
    assert response.submission_id == draft.id
    db.close()
    engine.dispose()


def test_reroll_respects_email_hourly_limit():
    db, engine = create_db()
    # 凑满每小时 3 条的同邮箱线索，其中第一条已完成诊断（可被复用会话）
    leads = [CompanyLead(company_name=f"公司{i}", email="same@example.com") for i in range(3)]
    for lead in leads:
        db.add(lead)
    db.flush()
    completed = DiagnosisSubmission(lead_id=leads[0].id, status=SubmissionStatus.scored.value)
    db.add(completed)
    db.commit()

    # 复用已完成会话开启新一轮：即使走轮换路径也必须受邮箱频控约束
    with pytest.raises(HTTPException) as exc_info:
        public.upsert_lead(
            make_payload(session_token=leads[0].session_token, email="same@example.com"),
            make_request(),
            db,
        )
    assert exc_info.value.status_code == 429
    db.close()
    engine.dispose()


def test_email_hourly_limit_cutoff_uses_utc_now_helper(monkeypatch):
    """频控截止时间取自 utc_now 助手：一小时内计入、超出一小时不计入、当前线索排除。

    固定时钟设在 2020 年，若实现回退到 datetime.utcnow()，真实当前时间远晚于
    固定时钟，"一小时内"的线索将全部落在截止时间之外，断言必然失败。
    """
    db, engine = create_db()
    fixed_now = datetime(2020, 1, 1, 12, 0, 0)  # 无时区 UTC，与 MySQL DATETIME 语义一致
    monkeypatch.setattr(public, "utc_now", lambda: fixed_now)

    lead_ids = []
    for i in range(3):
        lead = CompanyLead(
            company_name=f"公司{i}",
            email="same@example.com",
            created_at=fixed_now - timedelta(minutes=30),
        )
        db.add(lead)
        db.flush()
        lead_ids.append(lead.id)
    db.commit()

    # 一小时内已满 3 条：拒绝
    with pytest.raises(HTTPException) as exc_info:
        public.enforce_email_lead_limit(db, "same@example.com", None)
    assert exc_info.value.status_code == 429

    # 排除当前线索后仅 2 条：放行
    public.enforce_email_lead_limit(db, "same@example.com", lead_ids[0])

    # 超出一小时的线索不计入频控
    for i in range(10):
        db.add(CompanyLead(
            company_name=f"旧公司{i}",
            email="old@example.com",
            created_at=fixed_now - timedelta(hours=2),
        ))
    db.commit()
    public.enforce_email_lead_limit(db, "old@example.com", None)

    db.close()
    engine.dispose()

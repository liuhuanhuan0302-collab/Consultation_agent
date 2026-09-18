from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
HEAD_REVISION = "e3f7a9c2d501"


def _environment(database_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "ENVIRONMENT": "development",
            "SECRET_KEY": "migration-chain-test-secret",
        }
    )
    return environment


def _run(arguments: list[str], database_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=BACKEND_ROOT,
        env=_environment(database_path),
        check=False,
        capture_output=True,
        text=True,
    )


def _columns(database_path: Path, table_name: str) -> set[str]:
    with sqlite3.connect(database_path) as database:
        return {row[1] for row in database.execute(f"PRAGMA table_info({table_name})")}


def test_empty_database_upgrades_to_head(tmp_path: Path) -> None:
    database_path = tmp_path / "empty.db"

    result = _run(["scripts/migrate_database.py"], database_path)

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database_path) as database:
        revision = database.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert revision == HEAD_REVISION
    assert "city" in _columns(database_path, "company_leads")
    assert {"research_status", "pdf_status", "customer_pdf_bytes"} <= _columns(database_path, "reports")
    assert {
        "view_status",
        "first_viewed_at",
        "first_viewed_by",
        "processing_status",
        "processing_note",
        "export_status",
        "first_exported_at",
        "last_exported_at",
    } <= _columns(database_path, "company_leads")
    assert {
        "lock_token",
        "queue_state",
        "processing_stage",
        "approved_at",
        "approved_by",
        "task_kind",
        "task_context_json",
    } <= _columns(database_path, "report_delivery_jobs")
    assert "password_changed_at" in _columns(database_path, "users")
    with sqlite3.connect(database_path) as database:
        tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {
        "export_batches",
        "export_batch_leads",
        "report_queue_settings",
        "organization_reports",
        "organization_report_tasks",
    } <= tables
    with sqlite3.connect(database_path) as database:
        settings = database.execute(
            "SELECT processing_concurrency, active_queue_capacity, automatic_wait_capacity, "
            "pdf_concurrency, processing_paused, promotion_paused "
            "FROM report_queue_settings WHERE id = 1"
        ).fetchone()
    assert settings == (2, 50, 200, 1, 0, 0)


def test_complete_legacy_database_is_adopted_without_losing_data(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    baseline = _run(
        ["-m", "alembic", "-c", "alembic.ini", "upgrade", "2f1c343e7a91"],
        database_path,
    )
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    with sqlite3.connect(database_path) as database:
        database.execute(
            "INSERT INTO users (id,email,name,role,password_hash,is_active,created_at) "
            "VALUES (1,'legacy@example.com','Legacy','admin','hash',1,CURRENT_TIMESTAMP)"
        )
        database.execute(
            "INSERT INTO gateway_api_config "
            "(id,search_enabled,search_provider,search_timeout_seconds,search_max_results,updated_at) "
            "VALUES (1,0,'bocha',15,20,CURRENT_TIMESTAMP)"
        )
        database.execute(
            "INSERT INTO company_leads "
            "(id,session_token,company_name,lead_level,privacy_accepted,contact_authorized,created_at,updated_at) "
            "VALUES "
            "(10,'tok-10','Legacy Done','high',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),"
            "(11,'tok-11','Legacy Stuck','low',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),"
            "(12,'tok-12','Legacy Queued','medium',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        database.execute(
            "INSERT INTO diagnosis_submissions (id,lead_id,status,max_score,created_at,updated_at) "
            "VALUES (20,10,'submitted',100,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),"
            "(21,11,'submitted',100,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),"
            "(22,12,'submitted',100,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        database.execute(
            "INSERT INTO reports "
            "(id,submission_id,public_token,status,title,html_content,research_status,pdf_status,model_vendor,created_at,updated_at) "
            "VALUES "
            "(30,20,'tok-30','generated','R','<p>ok</p>','generated','generated','deepseek',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),"
            "(31,21,'tok-31','failed','R','','failed','pending','deepseek',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),"
            "(32,22,'tok-32','pending','R','','pending','pending','deepseek',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        database.execute(
            "UPDATE reports SET generation_error = '公司情报检索失败：测试' WHERE id = 31"
        )
        database.execute(
            "INSERT INTO report_delivery_jobs "
            "(id,lead_id,submission_id,report_id,recipient_email,status,attempts,max_attempts,run_after,created_at,updated_at) "
            "VALUES "
            "(40,10,20,30,'done@example.com','sent',1,3,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),"
            "(41,11,21,31,'stuck@example.com','failed',3,3,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        database.execute(
            "INSERT INTO report_delivery_jobs "
            "(id,lead_id,submission_id,report_id,recipient_email,status,attempts,max_attempts,run_after,created_at,updated_at) "
            "VALUES (42,12,22,32,'queued@example.com','queued',0,3,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        database.execute("DROP TABLE alembic_version")

    result = _run(["scripts/migrate_database.py"], database_path)

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database_path) as database:
        revision = database.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        email = database.execute("SELECT email FROM users WHERE id = 1").fetchone()[0]
        search_enabled, search_provider = database.execute(
            "SELECT search_enabled, search_provider FROM gateway_api_config WHERE id = 1"
        ).fetchone()
        lead_rows = {
            row[0]: row[1:]
            for row in database.execute(
                "SELECT id, view_status, export_status, processing_status, processing_note"
                " FROM company_leads WHERE id IN (10, 11)"
            ).fetchall()
        }
        delivery_queue_states = {
            row[0]: row[1]
            for row in database.execute(
                "SELECT id, queue_state FROM report_delivery_jobs WHERE id IN (40, 41, 42)"
            ).fetchall()
        }
    assert revision == HEAD_REVISION
    assert email == "legacy@example.com"
    assert search_enabled == 1
    assert search_provider == "deepseek"
    assert "city" in _columns(database_path, "company_leads")
    # 存量客户统一标记已经查看 + 已导出；处理状态按现状推导
    assert lead_rows[10] == ("viewed", "exported", "completed", None)
    # 错误自带「公司情报检索失败」前缀时不重复拼接
    assert lead_rows[11] == ("viewed", "exported", "manual_review", "公司情报检索失败：测试")
    assert delivery_queue_states == {40: None, 41: None, 42: "active"}


def test_partial_unversioned_database_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "partial.db"
    with sqlite3.connect(database_path) as database:
        database.execute("CREATE TABLE company_leads (id INTEGER PRIMARY KEY)")

    result = _run(["scripts/migrate_database.py"], database_path)

    assert result.returncode != 0
    assert "残缺数据库" in result.stderr


def test_precreated_queue_settings_table_is_adopted_and_values_preserved(tmp_path: Path) -> None:
    """The dev app can create settings through metadata before Alembic runs."""

    database_path = tmp_path / "precreated-settings.db"
    baseline = _run(
        ["-m", "alembic", "-c", "alembic.ini", "upgrade", "3e7d1b9c5a20"],
        database_path,
    )
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    with sqlite3.connect(database_path) as database:
        database.execute(
            "CREATE TABLE report_queue_settings ("
            "id INTEGER PRIMARY KEY, processing_concurrency INTEGER NOT NULL, "
            "active_queue_capacity INTEGER NOT NULL, automatic_wait_capacity INTEGER NOT NULL, "
            "pdf_concurrency INTEGER NOT NULL, processing_paused BOOLEAN NOT NULL, "
            "promotion_paused BOOLEAN NOT NULL, updated_by VARCHAR(120), updated_at DATETIME NOT NULL)"
        )
        database.execute(
            "INSERT INTO report_queue_settings "
            "VALUES (1, 4, 80, 300, 2, 1, 0, 'operator', CURRENT_TIMESTAMP)"
        )

    result = _run(["scripts/migrate_database.py"], database_path)

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database_path) as database:
        revision = database.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        values = database.execute(
            "SELECT processing_concurrency, active_queue_capacity, automatic_wait_capacity, "
            "pdf_concurrency, processing_paused, promotion_paused, updated_by "
            "FROM report_queue_settings WHERE id = 1"
        ).fetchone()
    assert revision == HEAD_REVISION
    assert values == (4, 80, 300, 2, 1, 0, "operator")


def test_precreated_task_kind_columns_and_index_are_adopted(tmp_path: Path) -> None:
    """c8 must tolerate task columns created by an ORM metadata bootstrap."""

    database_path = tmp_path / "precreated-task-columns.db"
    baseline = _run(
        ["-m", "alembic", "-c", "alembic.ini", "upgrade", "3e7d1b9c5a20"],
        database_path,
    )
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    with sqlite3.connect(database_path) as database:
        database.execute(
            "CREATE TABLE report_queue_settings ("
            "id INTEGER PRIMARY KEY, processing_concurrency INTEGER NOT NULL, "
            "active_queue_capacity INTEGER NOT NULL, automatic_wait_capacity INTEGER NOT NULL, "
            "pdf_concurrency INTEGER NOT NULL, processing_paused BOOLEAN NOT NULL, "
            "promotion_paused BOOLEAN NOT NULL, updated_by VARCHAR(120), updated_at DATETIME NOT NULL)"
        )
        database.execute(
            "INSERT INTO report_queue_settings VALUES "
            "(1, 2, 50, 200, 1, 0, 0, NULL, CURRENT_TIMESTAMP)"
        )
        database.execute(
            "ALTER TABLE report_delivery_jobs ADD COLUMN task_kind VARCHAR(32) "
            "NOT NULL DEFAULT 'full_delivery'"
        )
        database.execute("ALTER TABLE report_delivery_jobs ADD COLUMN task_context_json TEXT")
        database.execute("CREATE INDEX ix_report_delivery_jobs_task_kind ON report_delivery_jobs(task_kind)")
        # No parent rows are required for this migration-level preservation
        # check because SQLite's default foreign-key mode is disabled here.
        database.execute(
            "INSERT INTO report_delivery_jobs "
            "(id, lead_id, submission_id, report_id, recipient_email, status, attempts, max_attempts, "
            "run_after, created_at, updated_at, task_kind, task_context_json) VALUES "
            "(1, 1, 1, 1, 'customer@example.com', 'queued', 0, 3, CURRENT_TIMESTAMP, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'attachment_delivery', '{\"source\":\"legacy\"}')"
        )

    result = _run(["scripts/migrate_database.py"], database_path)

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database_path) as database:
        values = database.execute(
            "SELECT task_kind, task_context_json FROM report_delivery_jobs WHERE id = 1"
        ).fetchone()
        indexes = {row[1] for row in database.execute("PRAGMA index_list(report_delivery_jobs)")}
    assert values == ("attachment_delivery", '{"source":"legacy"}')
    assert "ix_report_delivery_jobs_task_kind" in indexes

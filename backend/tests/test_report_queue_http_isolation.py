"""HTTP and FastAPI lifecycle must never execute report pipeline work."""

import inspect

from app import main
from app.api.v1.endpoints import public
from app.api.v1.endpoints.admin import leads


def test_http_modules_have_no_background_report_execution() -> None:
    public_source = inspect.getsource(public)
    admin_source = inspect.getsource(leads)
    forbidden = (
        "BackgroundTasks",
        "background_tasks.add_task",
        "process_job_then_next",
        "process_next_report_delivery",
        "run_company_research_task",
        "run_report_regeneration_task",
        "regenerate_report_content_for_testing",
    )
    for marker in forbidden:
        assert marker not in public_source
        assert marker not in admin_source


def test_fastapi_startup_does_not_start_report_worker() -> None:
    source = inspect.getsource(main)
    assert "run_report_delivery_worker" not in source
    assert "report_worker_task" not in source

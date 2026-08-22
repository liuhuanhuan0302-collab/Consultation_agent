import pytest
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.models import Report
from app.service import pdf_service
from app.service.pdf_service import ReportPdfValidationError, validate_report_html, validate_report_pdf_bytes


def test_report_html_must_contain_every_customer_section():
    report = Report(submission_id=1, title="测试", html_content="<h2>一、执行摘要</h2>")

    with pytest.raises(ReportPdfValidationError, match="网页版报告缺少章节"):
        validate_report_html(report)


def test_tiny_or_invalid_pdf_is_never_delivered():
    with pytest.raises(ReportPdfValidationError, match="损坏或内容异常精简"):
        validate_report_pdf_bytes(b"%PDF-1.7\n")


def test_no_sandbox_flag_adds_launch_argument(monkeypatch, tmp_path):
    """容器环境开启 PDF_BROWSER_NO_SANDBOX 后，Chromium 以 --no-sandbox 启动。"""
    report = Report(submission_id=1, title="测试", html_content="<p>ok</p>", public_token="t")
    fake_browser = tmp_path / "fake-chrome"
    fake_browser.write_text("")
    monkeypatch.setattr(pdf_service, "browser_executable", lambda: str(fake_browser))
    monkeypatch.setattr(
        pdf_service,
        "get_settings",
        lambda: Settings(pdf_browser_no_sandbox=True),
    )
    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        pdf_arg = next(arg for arg in command if arg.startswith("--print-to-pdf="))
        Path(pdf_arg.split("=", 1)[1]).write_bytes(b"%PDF-1.7 placeholder")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(pdf_service.subprocess, "run", fake_run)

    assert pdf_service.render_report_pdf_bytes_with_browser(report) == b"%PDF-1.7 placeholder"
    assert "--no-sandbox" in captured["command"]


def test_sandbox_failure_error_hints_no_sandbox_flag(monkeypatch, tmp_path):
    """沙箱启动失败的报错必须提示运维开启 PDF_BROWSER_NO_SANDBOX（fail-closed）。"""
    report = Report(submission_id=1, title="测试", html_content="<p>ok</p>", public_token="t")
    fake_browser = tmp_path / "fake-chrome"
    fake_browser.write_text("")
    monkeypatch.setattr(pdf_service, "browser_executable", lambda: str(fake_browser))
    monkeypatch.setattr(
        pdf_service,
        "get_settings",
        lambda: Settings(pdf_browser_no_sandbox=False),
    )
    monkeypatch.setattr(
        pdf_service.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=1,
            stderr="zygote_host_impl_linux.cc:128] No usable sandbox!",
        ),
    )

    with pytest.raises(RuntimeError, match="PDF_BROWSER_NO_SANDBOX"):
        pdf_service.render_report_pdf_bytes_with_browser(report)

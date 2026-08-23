import json
import pytest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.request import url2pathname
from urllib.parse import urlparse

from app.config import Settings
from app.models import Report
from app.service import pdf_service
from app.service.pdf_service import (
    ReportPdfValidationError,
    customer_report_filename,
    validate_report_html,
    validate_report_pdf_bytes,
)


def test_report_html_must_contain_every_customer_section():
    report = Report(submission_id=1, title="测试", html_content="<h2>一、执行摘要</h2>")

    with pytest.raises(ReportPdfValidationError, match="网页版报告缺少章节"):
        validate_report_html(report)


def test_unparseable_pdf_is_never_delivered():
    """不以文件大小判断内容，格式无法解析时仍然阻止发送。"""
    with pytest.raises(ReportPdfValidationError, match="PDF 无法解析"):
        validate_report_pdf_bytes(b"%PDF-1.7\n")


def test_customer_pdf_template_excludes_internal_lead_and_research_fields():
    report = SimpleNamespace(
        id=123,
        title="江苏芯云电子科技 AI 原生转型诊断报告",
        created_at=datetime(2026, 8, 23),
        public_token="public-token",
        summary_json=json.dumps(
            {
                "score": {"total": 80, "max_score": 100, "score_rate": 0.8},
                "dimensions": [
                    {"module_code": "M01", "module_name": "一心：战略", "score_rate": 0.4},
                    {"module_code": "M02", "module_name": "简化业务", "score_rate": 0.8},
                ],
            },
            ensure_ascii=False,
        ),
        submission=SimpleNamespace(
            lead=SimpleNamespace(
                company_name="江苏芯云电子科技",
                contact_name="张三",
                phone="13800000000",
                email="internal@example.com",
                wechat="internal-wechat",
                source_code="wechat_mp",
            )
        ),
        html_content=(
            "<h2>一、执行摘要</h2><h2>二、能力成熟度分析</h2>"
            "<h2>三、关键矛盾与核心诊断</h2><h2>四、工作坊议题地图</h2>"
            "<h2>六、管理层行动建议</h2>"
        ),
    )

    html = pdf_service.render_report_html_attachment(report).decode("utf-8")

    assert "江苏芯云电子科技" in html
    assert "RPT-000123" in html
    assert "2026-08-23" in html
    assert "诊断总分" in html and "80" in html
    assert "满分" in html and "100" in html
    assert "综合得分率" in html and "80%" in html
    assert "能力成熟度排行" in html
    assert "AI 转型能力雷达图" in html
    assert "一心" in html and "简化业务" in html
    assert "<svg" in html
    assert "维度概览" not in html
    assert "在线报告" not in html
    for internal_label in ("联系人", "手机号", "邮箱", "微信", "来源", "首次查看人", "AI搜索"):
        assert internal_label not in html
    for internal_value in ("张三", "13800000000", "internal@example.com", "internal-wechat", "wechat_mp"):
        assert internal_value not in html


def test_customer_report_filename_is_readable_and_safe():
    report = SimpleNamespace(
        id=123,
        title="备用标题",
        submission=SimpleNamespace(lead=SimpleNamespace(company_name="奥飞/娱乐:*?")),
    )
    assert customer_report_filename(report) == "奥飞_娱乐_AI诊断报告.pdf"

    empty_company = SimpleNamespace(
        id=124,
        title="",
        submission=SimpleNamespace(lead=SimpleNamespace(company_name="<>:/\\|?*")),
    )
    assert customer_report_filename(empty_company) == "企业AI诊断报告.pdf"


def test_no_sandbox_flag_adds_launch_argument(monkeypatch, tmp_path):
    """容器环境开启 PDF_BROWSER_NO_SANDBOX 后，Chromium 以 --no-sandbox 启动。"""
    report = Report(
        submission_id=1,
        title="测试",
        html_content="<h2>一、执行摘要</h2>",
        public_token="t",
    )
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
        html_url = command[-1]
        assert html_url.startswith("file://")
        html_path = Path(url2pathname(urlparse(html_url).path))
        assert "一、执行摘要" in html_path.read_text(encoding="utf-8")
        Path(pdf_arg.split("=", 1)[1]).write_bytes(b"%PDF-1.7 placeholder")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(pdf_service.subprocess, "run", fake_run)

    assert pdf_service.render_report_pdf_bytes_with_browser(report) == b"%PDF-1.7 placeholder"
    assert "--no-sandbox" in captured["command"]
    assert "--disable-setuid-sandbox" in captured["command"]


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

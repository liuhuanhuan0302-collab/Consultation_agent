"""客户版 DOCX / Word→PDF 管道的测试：内容边界、评分头部、转换命令与 fallback。"""

import asyncio
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document
from docx.oxml.ns import qn
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

from app.core.config import Settings
from app.service import pdf_service
from app.service.lead_export_service import generate_customer_report_docx, generate_lead_export_docx


def _customer_report() -> SimpleNamespace:
    summary = {
        "score": {"total": 106, "max_score": 242, "score_rate": 106 / 242},
        "dimensions": [
            {"module_code": "M01", "module_name": "以用户/客户为中心", "score_rate": 0.25},
            {"module_code": "M02", "module_name": "简化业务", "score_rate": 0.61},
            {"module_code": "M03", "module_name": "流程化", "score_rate": 0.58},
        ],
    }
    html = (
        "<h2>一、执行摘要</h2><p>摘要内容。</p>"
        "<h2>二、能力成熟度分析</h2><p>按模块逐项分析。</p>"
        '<table class="report-finding-table"><thead><tr><th>序号</th><th>核心发现</th><th>证据与含义</th></tr></thead>'
        "<tbody><tr><td>1</td><td>流程需要优化</td><td>Q1 得分较低</td></tr></tbody></table>"
        "<h2>三、关键矛盾与核心诊断</h2><p>矛盾内容。</p>"
        "<h2>四、工作坊议题地图</h2><p>议题内容。</p>"
        "<h2>五、优先 AI 场景与案例</h2><p>场景内容。</p>"
        "<h2>六、管理层行动建议</h2><ol><li>建立数据治理机制</li></ol>"
    )
    return SimpleNamespace(
        id=7,
        title="奥飞娱乐 AI 原生转型诊断报告",
        created_at=datetime(2026, 8, 23),
        summary_json=json.dumps(summary, ensure_ascii=False),
        html_content=html,
    )


def _docx_text(document: Document) -> str:
    paragraphs = "\n".join(paragraph.text for paragraph in document.paragraphs)
    tables = "\n".join(
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    )
    return f"{paragraphs}\n{tables}"


def _tiny_pdf() -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4)
    document.build([Paragraph("test", getSampleStyleSheet()["Normal"])])
    return buffer.getvalue()


def test_customer_docx_excludes_internal_lead_and_research_fields() -> None:
    docx_bytes = generate_customer_report_docx(_customer_report(), "奥飞娱乐")
    document = Document(BytesIO(docx_bytes))
    text = _docx_text(document)

    assert "奥飞娱乐" in text
    assert "AI 原生转型诊断报告" in text
    assert "报告编号" in text and "RPT-000007" in text
    assert "报告日期" in text and "2026-08-23" in text
    for section in (
        "一、执行摘要",
        "二、能力成熟度分析",
        "三、关键矛盾与核心诊断",
        "四、工作坊议题地图",
        "五、优先 AI 场景与案例",
        "六、管理层行动建议",
    ):
        assert section in text
    for internal in (
        "一、基本信息",
        "二、企业公开信息与 AI 情报分析",
        "联系人",
        "手机号",
        "邮箱",
        "微信",
        "首次查看",
        "AI 情报",
        "公司介绍",
        "信息来源",
        "后台",
    ):
        assert internal not in text
    assert len(document.inline_shapes) == 2


def test_customer_docx_score_header_uses_summary_fields() -> None:
    docx_bytes = generate_customer_report_docx(_customer_report(), "奥飞娱乐")
    text = _docx_text(Document(BytesIO(docx_bytes)))

    assert "诊断总分" in text and "106" in text
    assert "满分" in text and "242" in text
    assert "综合得分率" in text and "44%" in text


@pytest.mark.parametrize(
    ("summary_json", "error_match"),
    [
        (None, "缺少 score 评分快照"),
        ("not-json", "不是有效 JSON"),
        (json.dumps({"score": {"total": True, "max_score": 100, "score_rate": 0.5}}), "非布尔数值"),
        (json.dumps({"score": {"total": float("nan"), "max_score": 100, "score_rate": 0.5}}), "有限数值"),
        (json.dumps({"score": {"total": -1, "max_score": 100, "score_rate": -0.01}}), "不得小于 0"),
        (json.dumps({"score": {"total": 101, "max_score": 100, "score_rate": 1.01}}), "不得大于"),
        (json.dumps({"score": {"total": 50, "max_score": 100, "score_rate": 0.7}}), "不一致"),
    ],
)
def test_invalid_persisted_score_blocks_all_pdf_renderers(
    monkeypatch,
    summary_json,
    error_match,
) -> None:
    report = _customer_report()
    report.summary_json = summary_json
    renderer_calls = {"docx": 0, "browser": 0}

    def forbidden_docx(_docx_bytes):
        renderer_calls["docx"] += 1
        raise AssertionError("无效评分不得进入 LibreOffice 渲染")

    def forbidden_browser(_html_bytes):
        renderer_calls["browser"] += 1
        raise AssertionError("无效评分不得进入 Chromium fallback")

    monkeypatch.setattr(pdf_service, "convert_customer_docx_to_pdf", forbidden_docx)
    monkeypatch.setattr(pdf_service, "render_report_pdf_bytes_with_browser_html", forbidden_browser)

    with pytest.raises(pdf_service.ReportPdfValidationError, match=error_match):
        asyncio.run(pdf_service.render_report_pdf_bytes(report))

    assert renderer_calls == {"docx": 0, "browser": 0}


def test_customer_docx_package_never_contains_internal_data_sentinels() -> None:
    report = _customer_report()
    report.company_research_json = json.dumps(
        {"company_overview": "RESEARCH_PRIVATE_SENTINEL", "sources": ["SEARCH_SOURCE_SENTINEL"]}
    )
    report.submission = SimpleNamespace(
        lead=SimpleNamespace(
            company_name="奥飞娱乐",
            contact_name="CONTACT_PRIVATE_SENTINEL",
            phone="PHONE_PRIVATE_SENTINEL",
            email="EMAIL_PRIVATE_SENTINEL",
            wechat="WECHAT_PRIVATE_SENTINEL",
            source_code="SOURCE_PRIVATE_SENTINEL",
            first_viewed_by="ADMIN_PRIVATE_SENTINEL",
        )
    )

    package = generate_customer_report_docx(report, "奥飞娱乐")
    with zipfile.ZipFile(BytesIO(package)) as archive:
        xml_payload = b"\n".join(
            archive.read(name)
            for name in archive.namelist()
            if name.endswith((".xml", ".rels"))
        ).decode("utf-8", errors="ignore")

    for sentinel in (
        "RESEARCH_PRIVATE_SENTINEL",
        "SEARCH_SOURCE_SENTINEL",
        "CONTACT_PRIVATE_SENTINEL",
        "PHONE_PRIVATE_SENTINEL",
        "EMAIL_PRIVATE_SENTINEL",
        "WECHAT_PRIVATE_SENTINEL",
        "SOURCE_PRIVATE_SENTINEL",
        "ADMIN_PRIVATE_SENTINEL",
    ):
        assert sentinel not in xml_payload


def test_customer_header_tables_have_fixed_grid_widths() -> None:
    document = Document(BytesIO(generate_customer_report_docx(_customer_report(), "奥飞娱乐")))

    assert len(document.tables) >= 3
    for table, column_count in zip(document.tables[:2], (2, 3)):
        layout = table._tbl.tblPr.find(qn("w:tblLayout"))
        assert layout is not None and layout.get(qn("w:type")) == "fixed"
        grid_widths = [int(column.get(qn("w:w"))) for column in table._tbl.tblGrid]
        assert len(grid_widths) == column_count
        assert len(set(grid_widths)) == 1
        cell_widths = [int(cell._tc.tcPr.tcW.get(qn("w:w"))) for cell in table.rows[0].cells]
        assert cell_widths == grid_widths


def test_render_prefers_docx_when_enabled(monkeypatch) -> None:
    report = _customer_report()
    valid_pdf = _tiny_pdf()
    called = {"docx": False, "browser": False}

    def fake_docx(docx_bytes):
        assert isinstance(docx_bytes, bytes) and docx_bytes.startswith(b"PK")
        called["docx"] = True
        return valid_pdf

    def fake_browser(html_bytes):
        assert isinstance(html_bytes, bytes)
        called["browser"] = True
        return valid_pdf

    monkeypatch.setattr(pdf_service, "convert_customer_docx_to_pdf", fake_docx)
    monkeypatch.setattr(pdf_service, "render_report_pdf_bytes_with_browser_html", fake_browser)

    assert asyncio.run(pdf_service.render_report_pdf_bytes(report)) == valid_pdf
    assert called == {"docx": True, "browser": False}


def test_docx_failure_falls_back_to_browser(monkeypatch) -> None:
    report = _customer_report()
    valid_pdf = _tiny_pdf()
    monkeypatch.setattr(
        pdf_service,
        "convert_customer_docx_to_pdf",
        lambda _bytes: (_ for _ in ()).throw(RuntimeError("LibreOffice 转换失败（模拟）")),
    )
    monkeypatch.setattr(
        pdf_service,
        "render_report_pdf_bytes_with_browser_html",
        lambda html_bytes: valid_pdf if isinstance(html_bytes, bytes) else b"",
    )

    assert asyncio.run(pdf_service.render_report_pdf_bytes(report)) == valid_pdf


def test_docx_failure_without_fallback_propagates(monkeypatch) -> None:
    report = _customer_report()
    monkeypatch.setattr(
        pdf_service,
        "get_settings",
        lambda: Settings(pdf_docx_fallback_to_browser=False),
    )
    monkeypatch.setattr(
        pdf_service,
        "convert_customer_docx_to_pdf",
        lambda _bytes: (_ for _ in ()).throw(RuntimeError("LibreOffice 转换失败（模拟）")),
    )

    with pytest.raises(RuntimeError, match="LibreOffice 转换失败"):
        asyncio.run(pdf_service.render_report_pdf_bytes(report))


def test_docx_disabled_uses_browser_directly(monkeypatch) -> None:
    report = _customer_report()
    valid_pdf = _tiny_pdf()
    monkeypatch.setattr(pdf_service, "get_settings", lambda: Settings(pdf_docx_render=False))
    monkeypatch.setattr(
        pdf_service,
        "convert_customer_docx_to_pdf",
        lambda _bytes: (_ for _ in ()).throw(AssertionError("docx 渲染不应被调用")),
    )
    monkeypatch.setattr(pdf_service, "render_report_pdf_bytes_with_browser_html", lambda _html: valid_pdf)

    assert asyncio.run(pdf_service.render_report_pdf_bytes(report)) == valid_pdf


def test_worker_threads_receive_bytes_instead_of_orm_report(monkeypatch) -> None:
    report = _customer_report()
    valid_pdf = _tiny_pdf()
    threaded_arguments: list[tuple[object, ...]] = []

    async def fake_to_thread(function, *args, **kwargs):
        threaded_arguments.append(args)
        assert args and all(isinstance(value, bytes) for value in args)
        return function(*args, **kwargs)

    monkeypatch.setattr(pdf_service.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(pdf_service, "convert_customer_docx_to_pdf", lambda _docx: valid_pdf)

    assert asyncio.run(pdf_service.render_report_pdf_bytes(report)) == valid_pdf
    assert len(threaded_arguments) == 1


def test_libreoffice_failure_preserves_root_cause_when_browser_disabled(monkeypatch) -> None:
    report = _customer_report()
    monkeypatch.setattr(
        pdf_service,
        "get_settings",
        lambda: Settings(pdf_docx_fallback_to_browser=True, pdf_browser_render=False),
    )
    monkeypatch.setattr(
        pdf_service,
        "convert_customer_docx_to_pdf",
        lambda _bytes: (_ for _ in ()).throw(RuntimeError("LO_ROOT_CAUSE_SENTINEL")),
    )

    with pytest.raises(RuntimeError, match="LO_ROOT_CAUSE_SENTINEL"):
        asyncio.run(pdf_service.render_report_pdf_bytes(report))


def test_libreoffice_conversion_invokes_soffice_and_returns_pdf(monkeypatch, tmp_path) -> None:
    fake_soffice = tmp_path / "soffice"
    fake_soffice.write_text("")
    monkeypatch.setattr(pdf_service, "libreoffice_executable", lambda: str(fake_soffice))
    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        outdir = Path(command[command.index("--outdir") + 1])
        captured["temp_root"] = outdir.parent
        assert captured["temp_root"].exists()
        assert (captured["temp_root"] / "lo-profile").is_dir()
        pdf_bytes = _tiny_pdf()
        (outdir / "customer-report.pdf").write_bytes(pdf_bytes)
        captured["pdf"] = pdf_bytes
        return SimpleNamespace(returncode=0, stdout="convert customer-report.docx as writer_pdf_Export", stderr="")

    monkeypatch.setattr(pdf_service.subprocess, "run", fake_run)

    docx_bytes = generate_customer_report_docx(_customer_report(), "奥飞娱乐")
    result = pdf_service.convert_customer_docx_to_pdf(docx_bytes)
    assert result == captured["pdf"]

    command = captured["command"]
    assert command[0] == str(fake_soffice)
    assert "--headless" in command
    assert "--convert-to" in command and "pdf:writer_pdf_Export" in command
    env_flag = next(arg for arg in command if arg.startswith("-env:UserInstallation="))
    assert env_flag.endswith("lo-profile")
    docx_arg = next(arg for arg in command if arg.endswith(".docx"))
    assert Path(docx_arg).name == "customer-report.docx"
    assert "--outdir" in command
    assert Path(command[command.index("--outdir") + 1]).name == "output"
    assert Path(docx_arg).parent.name == "input"
    assert not captured["temp_root"].exists()


def test_libreoffice_failure_reports_clear_error(monkeypatch, tmp_path) -> None:
    fake_soffice = tmp_path / "soffice"
    fake_soffice.write_text("")
    monkeypatch.setattr(pdf_service, "libreoffice_executable", lambda: str(fake_soffice))
    monkeypatch.setattr(
        pdf_service.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="writer stdout diagnostic",
            stderr="soffice crashed",
        ),
    )

    with pytest.raises(RuntimeError, match="stdout='writer stdout diagnostic'.*stderr='soffice crashed'"):
        pdf_service.convert_customer_docx_to_pdf(b"PK fake docx")


def test_libreoffice_timeout_reports_clear_error(monkeypatch, tmp_path) -> None:
    fake_soffice = tmp_path / "soffice"
    fake_soffice.write_text("")
    monkeypatch.setattr(pdf_service, "libreoffice_executable", lambda: str(fake_soffice))

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(pdf_service.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="转换超时"):
        pdf_service.convert_customer_docx_to_pdf(b"PK fake docx")


def test_libreoffice_timeout_configuration_is_bounded() -> None:
    with pytest.raises(ValueError):
        Settings(libreoffice_timeout=9)
    with pytest.raises(ValueError):
        Settings(libreoffice_timeout=601)


def test_configured_libreoffice_command_is_resolved_from_path(monkeypatch, tmp_path) -> None:
    executable = tmp_path / "custom-soffice"
    executable.write_text("")
    monkeypatch.setattr(
        pdf_service,
        "get_settings",
        lambda: Settings(libreoffice_executable="custom-soffice"),
    )
    monkeypatch.setattr(
        pdf_service.shutil,
        "which",
        lambda command: str(executable) if command == "custom-soffice" else None,
    )

    assert pdf_service.libreoffice_executable() == str(executable)


def test_invalid_configured_libreoffice_path_is_actionable(monkeypatch) -> None:
    monkeypatch.setattr(
        pdf_service,
        "get_settings",
        lambda: Settings(libreoffice_executable="missing-custom-soffice"),
    )
    monkeypatch.setattr(pdf_service.shutil, "which", lambda _command: None)

    with pytest.raises(RuntimeError, match="LIBREOFFICE_EXECUTABLE.*不可用"):
        pdf_service.libreoffice_executable()


def test_fixture_script_generates_docx_without_database_query(tmp_path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "ENVIRONMENT": "development",
            "DATABASE_URL": "sqlite:///:memory:",
            "LIBREOFFICE_EXECUTABLE": str(tmp_path / "intentionally-missing-soffice"),
        }
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_customer_report.py"
    result = subprocess.run(
        [sys.executable, "-B", str(script), "--fixture", "--outdir", str(tmp_path)],
        cwd=script.parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "奥飞娱乐_AI诊断报告.docx").exists()
    assert "已生成客户版 DOCX" in result.stdout
    assert "读取数据库失败" not in result.stdout

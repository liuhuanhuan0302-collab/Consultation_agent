import pytest

from app.models import Report
from app.service.pdf_service import ReportPdfValidationError, validate_report_html, validate_report_pdf_bytes


def test_report_html_must_contain_every_customer_section():
    report = Report(submission_id=1, title="测试", html_content="<h2>一、执行摘要</h2>")

    with pytest.raises(ReportPdfValidationError, match="网页版报告缺少章节"):
        validate_report_html(report)


def test_tiny_or_invalid_pdf_is_never_delivered():
    with pytest.raises(ReportPdfValidationError, match="损坏或内容异常精简"):
        validate_report_pdf_bytes(b"%PDF-1.7\n")

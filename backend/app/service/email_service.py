import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.config import get_settings


def send_report_pdf_email(to_email: str, report_title: str, pdf_bytes: bytes, filename: str) -> None:
    """通过 SMTP 将报告 PDF 作为附件发送到用户邮箱。"""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        raise RuntimeError("邮件服务未配置，请先配置 SMTP_HOST、SMTP_USERNAME、SMTP_PASSWORD")

    from_email = settings.smtp_from_email or settings.smtp_username
    message = EmailMessage()
    message["Subject"] = f"{report_title} PDF 报告"
    message["From"] = formataddr((settings.smtp_from_name, from_email))
    message["To"] = to_email
    message.set_content(
        f"""您好，

您申请领取的《{report_title}》已随邮件附件发送。

如需进一步解读报告或安排顾问沟通，可直接回复本邮件。

{settings.smtp_from_name}
""",
        subtype="plain",
        charset="utf-8",
    )
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)

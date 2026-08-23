import re
import json
import math
import logging
import shutil
import subprocess
import tempfile
import asyncio
from dataclasses import dataclass
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String

from app.core.config import get_settings
from app.models.report import Report
from app.service.lead_export_service import (
    CustomerReportScore,
    CustomerReportScoreError,
    customer_report_score,
    generate_customer_report_docx,
)
from app.service.report_content import sanitize_report_content


TAG_RE = re.compile(r"<[^>]+>")
REPORT_FILENAME_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
logger = logging.getLogger(__name__)

REPORT_SECTION_TITLES = [
    "一、执行摘要",
    "二、能力成熟度分析",
    "三、关键矛盾与核心诊断",
    "四、工作坊议题地图",
    "五、优先 AI 场景与案例",
    "六、管理层行动建议",
]
REPORT_SECTION_KEYWORDS = [
    "执行摘要",
    "能力成熟度分析",
    "关键矛盾与核心诊断",
    "工作坊议题地图",
    "管理层行动建议",
]


class ReportPdfValidationError(RuntimeError):
    """最终 PDF 与固定报告模板不一致，禁止发送给客户。"""


@dataclass(frozen=True, slots=True)
class CustomerReportSnapshot:
    """PDF 渲染所需的纯值快照，避免在线程中触发 ORM 懒加载。"""

    id: int | None
    title: str
    created_at: datetime | None
    summary_json: str | None
    html_content: str
    company_name: str


def report_company_name(report: Report) -> str:
    explicit_name = str(getattr(report, "company_name", "") or "").strip()
    if explicit_name:
        return explicit_name
    submission = getattr(report, "submission", None)
    lead = getattr(submission, "lead", None)
    company_name = str(getattr(lead, "company_name", "") or "").strip()
    if company_name:
        return company_name
    return str(report.title or "企业").split(" AI 原生转型诊断报告", 1)[0].strip() or "企业"


def customer_report_snapshot(report: Report) -> CustomerReportSnapshot:
    """在当前数据库线程复制渲染字段；后台线程只接收该纯值快照产生的 bytes。"""
    return CustomerReportSnapshot(
        id=getattr(report, "id", None),
        title=str(getattr(report, "title", "") or "AI 原生转型诊断报告"),
        created_at=getattr(report, "created_at", None),
        summary_json=getattr(report, "summary_json", None),
        html_content=str(getattr(report, "html_content", "") or ""),
        company_name=report_company_name(report),
    )


def customer_report_filename(report: Report) -> str:
    """返回客户可读的附件名，不暴露公开报告 token。"""
    company_name = REPORT_FILENAME_INVALID_CHARS_RE.sub("_", report_company_name(report))
    company_name = company_name.strip(" ._")
    if not company_name:
        return "企业AI诊断报告.pdf"
    return f"{company_name}_AI诊断报告.pdf"


def validate_report_html(report: Report) -> None:
    content = report.html_content or ""
    missing = [keyword for keyword in REPORT_SECTION_KEYWORDS if keyword not in content]
    if missing:
        raise ReportPdfValidationError(f"网页版报告缺少章节关键词：{', '.join(missing)}")


def validate_report_score_snapshot(report: Report) -> CustomerReportScore:
    """Fail closed before renderer selection when persisted scores are unsafe."""
    try:
        return customer_report_score(report)
    except CustomerReportScoreError as exc:
        raise ReportPdfValidationError(f"报告评分快照无效：{exc}") from exc


def validate_report_pdf_bytes(pdf_bytes: bytes) -> None:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ReportPdfValidationError("PDF 文件为空或格式无效")
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if not reader.pages:
            raise ReportPdfValidationError("PDF 没有有效页面")
    except ReportPdfValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ReportPdfValidationError(f"PDF 无法解析：{exc}") from exc


def register_cjk_font() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for path in candidates:
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("CJK", str(path)))
                return "CJK"
            except Exception:
                continue
    return "Helvetica"


def html_to_text(html: str) -> str:
    text = re.sub(r"</(h1|h2|h3|p|li|tr|section)>", "\n", html)
    text = TAG_RE.sub("", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _dimension_rate(item: dict) -> float:
    try:
        return max(0.0, min(float(item.get("score_rate") or 0), 1.0))
    except (TypeError, ValueError):
        return 0.0


def _dimension_name(item: dict) -> str:
    name = str(item.get("module_name") or item.get("module_code") or "")
    return name.split("：", 1)[0].strip() or "未命名维度"


def render_report_charts_html(dimensions: list[dict]) -> str:
    """将 summary_json 中的维度快照渲染为无脚本 SVG，供客户 PDF 打印。"""
    if not dimensions:
        return ""
    ordered = list(dimensions)
    sorted_dimensions = sorted(ordered, key=_dimension_rate)

    bar_width, bar_height, row_gap = 500, 26, 18
    bar_chart_height = 76 + len(sorted_dimensions) * (bar_height + row_gap)
    bar_rows: list[str] = []
    for index, item in enumerate(sorted_dimensions):
        y = 48 + index * (bar_height + row_gap)
        rate = _dimension_rate(item)
        label = escape(_dimension_name(item))
        bar_rows.append(
            f'<text x="0" y="{y + 18}" class="chart-label">{label}</text>'
            f'<rect x="150" y="{y}" width="290" height="{bar_height}" rx="6" class="bar-bg" />'
            f'<rect x="150" y="{y}" width="{290 * rate:.2f}" height="{bar_height}" rx="6" class="bar-fill" />'
            f'<text x="455" y="{y + 18}" class="chart-value">{round(rate * 100)}%</text>'
        )
    bar_svg = (
        f'<svg viewBox="0 0 {bar_width} {bar_chart_height}" role="img" '
        f'aria-label="能力成熟度排行图"><text x="0" y="20" class="svg-title">'
        f'能力成熟度排行</text>{"".join(bar_rows)}</svg>'
    )

    radar_width, radar_height, cx, cy, radius = 520, 400, 260, 215, 125

    def radar_point(index: int, value: float) -> tuple[float, float]:
        angle = -math.pi / 2 + 2 * math.pi * index / len(ordered)
        return cx + math.cos(angle) * radius * value, cy + math.sin(angle) * radius * value

    ring_polygons: list[str] = []
    axis_lines: list[str] = []
    for ring in range(1, 6):
        points = [radar_point(index, ring / 5) for index in range(len(ordered))]
        point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        ring_polygons.append(f'<polygon points="{point_text}" class="radar-ring" />')
    for index, item in enumerate(ordered):
        x, y = radar_point(index, 1)
        label_x, label_y = radar_point(index, 1.18)
        axis_lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" class="radar-axis" />')
        axis_lines.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" class="radar-label">'
            f'{escape(_dimension_name(item))}</text>'
        )
    value_points = [radar_point(index, _dimension_rate(item)) for index, item in enumerate(ordered)]
    value_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in value_points)
    value_nodes = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" class="radar-point" />' for x, y in value_points
    )
    radar_svg = (
        f'<svg viewBox="0 0 {radar_width} {radar_height}" role="img" '
        f'aria-label="AI 转型能力雷达图"><text x="0" y="20" class="svg-title">'
        f'AI 转型能力雷达图</text>{"".join(ring_polygons)}{"".join(axis_lines)}'
        f'<polygon points="{value_text}" class="radar-value" />{value_nodes}</svg>'
    )
    return f"""
    <section class="chart-grid">
      <div class="chart-card"><div class="chart-card-header"><span class="card-accent"></span>
        <h3>能力成熟度排行</h3><p>按当前启用维度的得分率从低到高排列</p></div>{bar_svg}</div>
      <div class="chart-card"><div class="chart-card-header"><span class="card-accent radar-accent"></span>
        <h3>AI 转型能力雷达图</h3><p>按当前启用维度生成，面积越大代表能力越均衡</p></div>{radar_svg}</div>
    </section>
    """


def rate_color(rate: float) -> colors.Color:
    """按得分率分档着色，替代已从 summary_json 下线的风险等级字段。"""
    if rate < 0.25:
        return colors.HexColor("#ef4444")
    if rate < 0.5:
        return colors.HexColor("#f59e0b")
    if rate < 0.75:
        return colors.HexColor("#3b82f6")
    return colors.HexColor("#22c55e")


def report_dimensions(report: Report) -> list[dict]:
    try:
        summary = json.loads(report.summary_json or "{}")
    except json.JSONDecodeError:
        return []
    return summary.get("dimensions") or []


def report_public_url(report: Report) -> str:
    settings = get_settings()
    return f"{settings.public_web_base_url.rstrip('/')}/report/{quote(report.public_token)}"


def make_bar_chart(dimensions: list[dict], font_name: str) -> Drawing:
    width, height = 500, 230
    drawing = Drawing(width, height)
    drawing.add(String(0, height - 12, "维度得分排行", fontName=font_name, fontSize=12, fillColor=colors.HexColor("#334155")))
    sorted_dimensions = sorted(dimensions, key=lambda item: item.get("score_rate", 0))
    chart_left, chart_top = 110, height - 32
    bar_height, gap, max_width = 12, 8, 330
    for index, dimension in enumerate(sorted_dimensions):
        y = chart_top - index * (bar_height + gap)
        rate = float(dimension.get("score_rate", 0))
        name = str(dimension.get("module_name") or dimension.get("module_code") or "")[:12]
        drawing.add(String(0, y + 2, name, fontName=font_name, fontSize=8, fillColor=colors.HexColor("#475467")))
        drawing.add(Rect(chart_left, y, max_width, bar_height, fillColor=colors.HexColor("#f1f5f9"), strokeColor=None))
        drawing.add(Rect(chart_left, y, max_width * min(rate, 1), bar_height, fillColor=rate_color(rate), strokeColor=None))
        drawing.add(String(chart_left + max_width + 8, y + 2, f"{round(rate * 100)}%", fontName=font_name, fontSize=8, fillColor=colors.HexColor("#475467")))
    return drawing


def make_radar_chart(dimensions: list[dict], font_name: str) -> Drawing:
    width, height = 500, 260
    drawing = Drawing(width, height)
    drawing.add(String(0, height - 12, "能力雷达图", fontName=font_name, fontSize=12, fillColor=colors.HexColor("#334155")))
    if not dimensions:
        return drawing
    cx, cy, radius = width / 2, height / 2 - 8, 82
    count = len(dimensions)
    for ring in range(1, 6):
        r = radius * ring / 5
        points: list[float] = []
        for index in range(count):
            angle = -math.pi / 2 + 2 * math.pi * index / count
            points.extend([cx + math.cos(angle) * r, cy + math.sin(angle) * r])
        drawing.add(Polygon(points, strokeColor=colors.HexColor("#e2e8f0"), fillColor=None))
    value_points: list[float] = []
    for index, dimension in enumerate(dimensions):
        angle = -math.pi / 2 + 2 * math.pi * index / count
        axis_x, axis_y = cx + math.cos(angle) * radius, cy + math.sin(angle) * radius
        drawing.add(Line(cx, cy, axis_x, axis_y, strokeColor=colors.HexColor("#e2e8f0")))
        label = str(dimension.get("module_code") or "")[:5]
        drawing.add(String(axis_x - 10, axis_y - 4, label, fontName=font_name, fontSize=8, fillColor=colors.HexColor("#475467")))
        rate = float(dimension.get("score_rate", 0))
        px, py = cx + math.cos(angle) * radius * min(rate, 1), cy + math.sin(angle) * radius * min(rate, 1)
        value_points.extend([px, py])
        drawing.add(Circle(px, py, 3, fillColor=rate_color(rate), strokeColor=colors.white))
    drawing.add(Polygon(value_points, strokeColor=colors.HexColor("#3b82f6"), fillColor=colors.Color(0.23, 0.51, 0.96, alpha=0.18)))
    return drawing


async def render_report_pdf_bytes(report: Report) -> bytes:
    """渲染客户 PDF：优先 Word→PDF（LibreOffice），失败时按配置回退 Chromium。

    客户 PDF 与内部 Word 档案第三部分共用同一套 Word 排版组件，保证
    字体、深蓝表头、表格列宽、行距和图表在两份文档中一致。
    """
    settings = get_settings()
    # Report 可能仍绑定 SQLAlchemy Session。所有属性和关系都必须在当前
    # 事件循环线程取值；to_thread 只接收已经生成的 DOCX/HTML bytes，避免
    # 在线程内触发 expire_on_commit 刷新或 submission/lead 懒加载。
    snapshot = customer_report_snapshot(report)
    validate_report_html(snapshot)
    persisted_score = validate_report_score_snapshot(snapshot)
    fallback_html: bytes | None = None
    if settings.pdf_docx_render:
        try:
            docx_bytes = generate_customer_report_docx(
                snapshot,
                snapshot.company_name,
                score=persisted_score,
            )
            pdf_bytes = await asyncio.to_thread(convert_customer_docx_to_pdf, docx_bytes)
            validate_report_pdf_bytes(pdf_bytes)
            return pdf_bytes
        except Exception as exc:
            logger.warning("Word→PDF 客户报告渲染失败，将评估 Chromium fallback：%s", exc, exc_info=True)
            if not (settings.pdf_docx_fallback_to_browser and settings.pdf_browser_render):
                logger.error(
                    "Word→PDF 失败且 Chromium fallback 不可用：fallback_enabled=%s browser_enabled=%s",
                    settings.pdf_docx_fallback_to_browser,
                    settings.pdf_browser_render,
                )
                raise
            logger.info("按配置回退 Chromium HTML→PDF 渲染")
            fallback_html = render_report_html_attachment(snapshot)
    if not settings.pdf_browser_render:
        raise ReportPdfValidationError("Word 与浏览器 PDF 渲染均未启用，已阻止发送报告")
    if fallback_html is None:
        fallback_html = render_report_html_attachment(snapshot)
    pdf_bytes = await asyncio.to_thread(render_report_pdf_bytes_with_browser_html, fallback_html)
    validate_report_pdf_bytes(pdf_bytes)
    return pdf_bytes


def libreoffice_executable() -> str:
    configured = str(get_settings().libreoffice_executable or "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        resolved = shutil.which(configured) or (str(configured_path) if configured_path.is_file() else None)
        if resolved:
            return resolved
        raise RuntimeError(f"LIBREOFFICE_EXECUTABLE 指向不可用的文件或命令：{configured}")

    for command in ("libreoffice", "soffice"):
        resolved = shutil.which(command)
        if resolved:
            return resolved

    candidates = [
        "C:/Program Files/LibreOffice/program/soffice.exe",
        "C:/Program Files/LibreOffice/program/soffice.com",
        "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
        "C:/Program Files (x86)/LibreOffice/program/soffice.com",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("未找到 LibreOffice（soffice），无法执行 Word→PDF 转换")


def convert_customer_docx_to_pdf(docx_bytes: bytes) -> bytes:
    """把已构建的客户 DOCX bytes 用 LibreOffice Writer 转成 PDF。

    每个任务使用独立临时目录与独立 LibreOffice 用户配置目录
    （UserInstallation），避免并发任务争用同一 profile 导致转换失败；
    转换结束（含失败）后由 TemporaryDirectory 清理全部临时文件。
    """
    settings = get_settings()
    soffice = libreoffice_executable()
    with tempfile.TemporaryDirectory(prefix="report-docx-pdf-") as tmp:
        directory = Path(tmp)
        input_dir = directory / "input"
        output_dir = directory / "output"
        profile_dir = directory / "lo-profile"
        input_dir.mkdir()
        output_dir.mkdir()
        profile_dir.mkdir()
        docx_path = input_dir / "customer-report.docx"
        docx_path.write_bytes(docx_bytes)
        profile_uri = profile_dir.as_uri()
        command = [
            soffice,
            "--headless",
            "--invisible",
            "--norestore",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ]
        logger.info(
            "开始 LibreOffice Writer 客户报告转换：executable=%s timeout=%ss",
            Path(soffice).name,
            settings.libreoffice_timeout,
        )
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=settings.libreoffice_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error("LibreOffice Word→PDF 转换超时：timeout=%ss", settings.libreoffice_timeout)
            raise RuntimeError(f"LibreOffice Word→PDF 转换超时（{settings.libreoffice_timeout} 秒）") from exc
        pdf_path = output_dir / f"{docx_path.stem}.pdf"
        stdout = (getattr(result, "stdout", "") or "").strip()[-1000:]
        stderr = (getattr(result, "stderr", "") or "").strip()[-1000:]
        if result.returncode != 0 or not pdf_path.exists():
            logger.error(
                "LibreOffice Word→PDF 转换失败：code=%s output_exists=%s stdout=%r stderr=%r",
                result.returncode,
                pdf_path.exists(),
                stdout,
                stderr,
            )
            raise RuntimeError(
                "LibreOffice Word→PDF 转换失败: "
                f"code={result.returncode}, output_exists={pdf_path.exists()}, "
                f"stdout={stdout!r}, stderr={stderr!r}"
            )
        pdf_bytes = pdf_path.read_bytes()
        logger.info(
            "LibreOffice Writer 客户报告转换完成：pdf_bytes=%s stdout=%r stderr=%r",
            len(pdf_bytes),
            stdout,
            stderr,
        )
        return pdf_bytes


def render_report_pdf_bytes_docx(report: Report) -> bytes:
    """同步兼容入口；正式异步管道会先快照 ORM，再仅在线程中转换 bytes。"""
    snapshot = customer_report_snapshot(report)
    docx_bytes = generate_customer_report_docx(snapshot, snapshot.company_name)
    return convert_customer_docx_to_pdf(docx_bytes)


def browser_executable() -> str:
    candidates = [
        get_settings().pdf_browser_executable,
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("msedge"),
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("未找到 Chrome/Edge/Chromium，无法使用浏览器渲染 PDF")


def render_report_pdf_bytes_with_browser_html(html_bytes: bytes) -> bytes:
    """使用 Chromium 打印已经在调用线程生成的自包含 HTML bytes。"""
    settings = get_settings()
    browser = browser_executable()
    with tempfile.TemporaryDirectory(prefix="report-pdf-") as tmp:
        # 公开报告页是 Vue SPA，需要先请求接口再完成 hydration。直接打印该
        # URL 会受网络、接口响应和固定 virtual-time-budget 影响，可能在章节
        # 尚未挂载时生成一个“看起来成功但内容不完整”的 PDF。附件 HTML
        # 已经由后端根据同一份已校验的 report.html_content 生成，使用它作为
        # 本地、自包含的打印源可以消除这条异步链路。
        html_path = Path(tmp) / "report.html"
        html_path.write_bytes(html_bytes)
        pdf_path = Path(tmp) / "report.pdf"
        profile_path = Path(tmp) / "profile"
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            "--print-to-pdf-no-header",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile_path}",
            "--virtual-time-budget=3000",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        # 容器环境（security_opt: no-new-privileges + cap_drop: ALL）中 Chromium
        # 沙箱无法启动（setuid helper 被 no-new-privileges 禁止、宿主 AppArmor
        # 又限制非特权用户命名空间）。此时容器本身即隔离边界，且渲染内容为本
        # 系统生成并净化过的报告 HTML，按 Playwright 容器部署惯例加 --no-sandbox。
        # 非容器环境保持沙箱开启，默认关闭该开关。
        if settings.pdf_browser_no_sandbox:
            command.insert(1, "--no-sandbox")
            command.insert(2, "--disable-setuid-sandbox")
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode != 0 or not pdf_path.exists():
            stderr = result.stderr[-500:]
            hint = ""
            if "No usable sandbox" in stderr and not settings.pdf_browser_no_sandbox:
                hint = (
                    "；容器/受限环境请设置 PDF_BROWSER_NO_SANDBOX=true"
                    "（容器已通过 cap_drop 与 no-new-privileges 隔离）"
                )
            raise RuntimeError(
                f"浏览器打印 PDF 失败: code={result.returncode}, stderr={stderr}{hint}"
            )
        return pdf_path.read_bytes()


def render_report_pdf_bytes_with_browser(report: Report) -> bytes:
    """同步兼容入口；正式异步管道不会把 ORM Report 传入后台线程。"""
    snapshot = customer_report_snapshot(report)
    return render_report_pdf_bytes_with_browser_html(render_report_html_attachment(snapshot))


def render_report_pdf_bytes_fallback(report: Report) -> bytes:
    buffer = BytesIO()
    font_name = register_cjk_font()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title=report.title,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "ChineseNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1f2937"),
    )
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#111827"),
    )
    story = [Paragraph(report.title, title), Spacer(1, 16)]
    dimensions = report_dimensions(report)
    if dimensions:
        story.extend([make_bar_chart(dimensions, font_name), Spacer(1, 14), make_radar_chart(dimensions, font_name), Spacer(1, 14)])
    for line in html_to_text(sanitize_report_content(report.html_content)).splitlines():
        story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), normal))
        story.append(Spacer(1, 6))
    document.build(story)
    return buffer.getvalue()


def render_report_html_attachment(report: Report) -> bytes:
    try:
        summary = json.loads(report.summary_json or "{}")
    except json.JSONDecodeError:
        summary = {}
    company_name = report_company_name(report)
    report_number = f"RPT-{report.id:06d}" if isinstance(report.id, int) else "RPT-UNKNOWN"
    report_date = report.created_at.strftime("%Y-%m-%d") if report.created_at else "-"
    score = summary.get("score") or {}
    dimensions = summary.get("dimensions") or []
    charts = render_report_charts_html(dimensions)
    score_rate = score.get("score_rate")
    score_rate_text = "-" if score_rate is None else f"{round(float(score_rate) * 100)}%"
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(company_name)} - AI原生转型诊断报告</title>
  <style>
    body {{ margin: 0; background: #eef3f8; color: #18202f; font-family: "Microsoft YaHei", Arial, sans-serif; }}
    .shell {{ max-width: 1080px; margin: 0 auto; padding: 42px 24px 56px; }}
    .hero {{ background: linear-gradient(135deg, #0c1f3a, #1a3f60); border-radius: 18px; color: #fff; padding: 52px 56px; }}
    .hero p {{ color: #b8c7db; margin: 0 0 12px; }}
    .hero h1 {{ font-size: 36px; line-height: 1.25; margin: 0 0 10px; }}
    .hero .subtitle {{ color: #e2e8f0; font-size: 20px; margin-bottom: 30px; }}
    .report-meta {{ border-top: 1px solid rgba(255,255,255,.25); display: grid; grid-template-columns: 1fr 1fr; gap: 18px 36px; margin: 0; padding-top: 24px; }}
    .report-meta div {{ display: flex; justify-content: space-between; gap: 24px; }}
    .report-meta dt {{ color: #b8c7db; }}
    .report-meta dd {{ margin: 0; color: #fff; font-weight: 700; }}
    .score-strip {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 28px 0; }}
    .score-card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px 26px; }}
    .score-card span {{ color: #94a3b8; display: block; font-size: 12px; font-weight: 700; margin-bottom: 8px; }}
    .score-card strong {{ color: #0f172a; display: block; font-size: 34px; line-height: 1; }}
    .score-card em {{ color: #94a3b8; font-size: 18px; font-style: normal; }}
    .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 28px 0; }}
    .chart-card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 24px 24px 18px; break-inside: avoid; }}
    .chart-card-header {{ margin-bottom: 10px; }}
    .card-accent {{ display: block; width: 34px; height: 4px; border-radius: 4px; background: linear-gradient(135deg,#2563eb,#38bdf8); margin-bottom: 10px; }}
    .radar-accent {{ background: linear-gradient(135deg,#8b5cf6,#6366f1); }}
    .chart-card h3 {{ color: #0f172a; font-size: 16px; margin: 0 0 4px; }}
    .chart-card p {{ color: #94a3b8; font-size: 12px; margin: 0; }}
    .chart-card svg {{ display: block; width: 100%; height: auto; margin-top: 14px; overflow: visible; }}
    .svg-title {{ fill: #334155; font-size: 14px; font-weight: 700; }}
    .chart-label, .chart-value {{ fill: #475569; font-size: 11px; }}
    .chart-value {{ font-weight: 700; }}
    .bar-bg {{ fill: #e2e8f0; }}
    .bar-fill {{ fill: #3b82f6; }}
    .radar-ring {{ fill: none; stroke: #dbe4ef; stroke-width: 1; }}
    .radar-axis {{ stroke: #dbe4ef; stroke-width: 1; }}
    .radar-label {{ fill: #475569; font-size: 11px; }}
    .radar-value {{ fill: rgba(59,130,246,.16); stroke: #3b82f6; stroke-width: 2.5; }}
    .radar-point {{ fill: #22c55e; stroke: #fff; stroke-width: 2; }}
    .report-html {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; margin-top: 28px; padding: 38px 46px; page-break-before: always; }}
    h2 {{ border-top: 1px solid #e2e8f0; color: #0f172a; font-size: 20px; margin: 32px 0 16px; padding-top: 24px; }}
    h3 {{ color: #1e293b; font-size: 17px; margin: 22px 0 10px; }}
    p, li {{ color: #475569; font-size: 15px; line-height: 1.85; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 12px; text-align: left; }}
    th {{ color: #334155; background: #f8fafc; }}
    @media (max-width: 760px) {{
      .shell {{ padding: 18px; }}
      .hero {{ padding: 28px 24px; }}
      .score-strip {{ grid-template-columns: 1fr; }}
      .chart-grid {{ grid-template-columns: 1fr; }}
      .report-meta {{ grid-template-columns: 1fr; }}
      .report-html {{ padding: 26px 22px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <p>AI 原生企业转型诊断报告</p>
      <h1>{escape(company_name)}</h1>
      <p class="subtitle">AI 原生转型诊断报告</p>
      <dl class="report-meta">
        <div><dt>报告编号</dt><dd>{escape(report_number)}</dd></div>
        <div><dt>报告日期</dt><dd>{escape(report_date)}</dd></div>
      </dl>
    </section>
    <section class="score-strip">
      <div class="score-card"><span>诊断总分</span><strong>{escape(str(score.get("total", "-")))}</strong></div>
      <div class="score-card"><span>满分</span><strong>{escape(str(score.get("max_score", "-")))}</strong></div>
      <div class="score-card"><span>综合得分率</span><strong>{escape(score_rate_text)}</strong></div>
    </section>
    {charts}
    <article class="report-html">{sanitize_report_content(report.html_content)}</article>
  </main>
</body>
</html>"""
    return html.encode("utf-8")

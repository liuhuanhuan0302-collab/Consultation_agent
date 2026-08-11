import re
import json
import math
import logging
import shutil
import subprocess
import tempfile
import asyncio
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String

from app.config import get_settings
from app.models import Report


TAG_RE = re.compile(r"<[^>]+>")
logger = logging.getLogger(__name__)


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


def risk_color(level: str) -> colors.Color:
    palette = {
        "高风险": colors.HexColor("#ef4444"),
        "较弱": colors.HexColor("#f59e0b"),
        "良好": colors.HexColor("#3b82f6"),
        "优秀": colors.HexColor("#22c55e"),
    }
    return palette.get(level, colors.HexColor("#94a3b8"))


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
        level = str(dimension.get("risk_level") or "")
        drawing.add(String(0, y + 2, name, fontName=font_name, fontSize=8, fillColor=colors.HexColor("#475467")))
        drawing.add(Rect(chart_left, y, max_width, bar_height, fillColor=colors.HexColor("#f1f5f9"), strokeColor=None))
        drawing.add(Rect(chart_left, y, max_width * min(rate, 1), bar_height, fillColor=risk_color(level), strokeColor=None))
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
        drawing.add(Circle(px, py, 3, fillColor=risk_color(str(dimension.get("risk_level") or "")), strokeColor=colors.white))
    drawing.add(Polygon(value_points, strokeColor=colors.HexColor("#3b82f6"), fillColor=colors.Color(0.23, 0.51, 0.96, alpha=0.18)))
    return drawing


async def render_report_pdf_bytes(report: Report) -> bytes:
    settings = get_settings()
    if settings.pdf_browser_render:
        try:
            return await asyncio.to_thread(render_report_pdf_bytes_with_browser, report)
        except Exception:
            logger.exception("浏览器渲染 PDF 失败，降级为文本版 PDF: report_id=%s", report.id)
    return render_report_pdf_bytes_fallback(report)


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


def render_report_pdf_bytes_with_browser(report: Report) -> bytes:
    url = report_public_url(report)
    browser = browser_executable()
    with tempfile.TemporaryDirectory(prefix="report-pdf-") as tmp:
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
            f"--user-data-dir={profile_path}",
            "--virtual-time-budget=3000",
            f"--print-to-pdf={pdf_path}",
            url,
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode != 0 or not pdf_path.exists():
            raise RuntimeError(
                f"浏览器打印 PDF 失败: code={result.returncode}, stderr={result.stderr[-500:]}"
            )
        return pdf_path.read_bytes()


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
    for line in html_to_text(report.html_content).splitlines():
        story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), normal))
        story.append(Spacer(1, 6))
    document.build(story)
    return buffer.getvalue()


def render_report_html_attachment(report: Report) -> bytes:
    try:
        summary = json.loads(report.summary_json or "{}")
    except json.JSONDecodeError:
        summary = {}
    score = summary.get("score") or {}
    dimensions = summary.get("dimensions") or []
    public_url = report_public_url(report)
    cards = ""
    if score:
        cards = f"""
        <section class="score-strip">
          <div class="score-card"><span>诊断总分</span><strong>{escape(str(score.get("total", "-")))}<em>/{escape(str(score.get("max_score", 260)))}</em></strong></div>
          <div class="score-card"><span>就绪度等级</span><strong>{escape(str(score.get("risk_level", "-")))}</strong></div>
          <div class="score-card"><span>综合得分率</span><strong>{round(float(score.get("score_rate") or 0) * 100)}<em>%</em></strong></div>
        </section>
        """
    dimension_rows = "".join(
        f"<tr><td>{escape(str(item.get('module_name') or item.get('module_code') or ''))}</td>"
        f"<td>{round(float(item.get('score_rate') or 0) * 100)}%</td>"
        f"<td>{escape(str(item.get('risk_level') or ''))}</td></tr>"
        for item in dimensions
    )
    dimension_table = f"""
    <section class="html-section">
      <h2>维度概览</h2>
      <table><thead><tr><th>维度</th><th>得分率</th><th>等级</th></tr></thead><tbody>{dimension_rows}</tbody></table>
    </section>
    """ if dimension_rows else ""
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(report.title)}</title>
  <style>
    body {{ margin: 0; background: #eef3f8; color: #18202f; font-family: "Microsoft YaHei", Arial, sans-serif; }}
    .shell {{ max-width: 1080px; margin: 0 auto; padding: 42px 24px 56px; }}
    .hero {{ background: linear-gradient(135deg, #0c1f3a, #1a3f60); border-radius: 18px; color: #fff; padding: 42px 48px; }}
    .hero p {{ color: #b8c7db; margin: 0 0 12px; }}
    .hero h1 {{ font-size: 32px; line-height: 1.25; margin: 0 0 14px; }}
    .hero a {{ color: #bfdbfe; }}
    .score-strip {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 28px 0; }}
    .score-card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px 26px; }}
    .score-card span {{ color: #94a3b8; display: block; font-size: 12px; font-weight: 700; margin-bottom: 8px; }}
    .score-card strong {{ color: #0f172a; display: block; font-size: 34px; line-height: 1; }}
    .score-card em {{ color: #94a3b8; font-size: 18px; font-style: normal; }}
    .html-section, .report-html {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; margin-top: 28px; padding: 38px 46px; }}
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
      .html-section, .report-html {{ padding: 26px 22px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <p>AI 原生企业转型诊断报告</p>
      <h1>{escape(report.title)}</h1>
      <p>在线报告：<a href="{escape(public_url)}">{escape(public_url)}</a></p>
    </section>
    {cards}
    {dimension_table}
    <article class="report-html">{report.html_content}</article>
  </main>
</body>
</html>"""
    return html.encode("utf-8")

import re
import json
import math
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String

from app.models import Report


TAG_RE = re.compile(r"<[^>]+>")


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


def render_report_pdf_bytes(report: Report) -> bytes:
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

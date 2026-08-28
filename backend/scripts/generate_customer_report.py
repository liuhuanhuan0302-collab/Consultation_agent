"""本地生成客户版 DOCX/PDF 视觉验收件（不发送邮件）。

用法（在 backend 目录下执行）：
    python scripts/generate_customer_report.py --company 奥飞     # 按公司名匹配最近一份报告（连数据库）
    python scripts/generate_customer_report.py 7                  # 按报告 id（连数据库）
    python scripts/generate_customer_report.py --fixture          # 内置合成数据，无需数据库
    python scripts/generate_customer_report.py --fixture --browser-preview

输出到 backend/output/：
    {公司}_AI诊断报告.docx —— 与内部 Word 第三部分共用同一套排版组件的客户版
    {公司}_AI诊断报告.pdf           —— 本机装有 LibreOffice 时生成

``--browser-preview`` 仅生成独立的浏览器预览验收件；它不是邮件附件来源。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.service.lead_export_service import generate_customer_report_docx  # noqa: E402
from app.service.pdf_service import (  # noqa: E402
    REPORT_FILENAME_INVALID_CHARS_RE,
    convert_customer_docx_to_pdf,
    render_report_html_attachment,
    render_report_pdf_bytes_with_browser_html,
    validate_report_pdf_bytes,
)

OUTPUT_DIR = BACKEND_ROOT / "output"


def _fixture_report() -> SimpleNamespace:
    """内置合成数据：覆盖获批客户报告的全部结构，不读取客户数据库。"""
    summary = {
        "report_format_version": 2,
        "report_contact": {
            "contact_name": "优小越",
            "phone": "17646848610",
            "wechat": "18664874363",
            "email": "youxiaoyue@youkunai.cn",
        },
        "score": {"total": 134, "max_score": 242, "score_rate": 134 / 242},
        "dimensions": [
            {"module_code": "M01", "module_name": "一心：以用户/客户为中心", "raw_score": 20, "max_score": 28, "score_rate": 20 / 28},
            {"module_code": "M02", "module_name": "简化业务", "raw_score": 14, "max_score": 28, "score_rate": 0.50},
            {"module_code": "M03", "module_name": "组织简练", "raw_score": 13, "max_score": 28, "score_rate": 13 / 28},
            {"module_code": "M04", "module_name": "团队协同", "raw_score": 14, "max_score": 28, "score_rate": 0.50},
            {"module_code": "M05", "module_name": "流程化", "raw_score": 14, "max_score": 28, "score_rate": 0.50},
            {"module_code": "M06", "module_name": "自动化", "raw_score": 9, "max_score": 27, "score_rate": 1 / 3},
            {"module_code": "M07", "module_name": "数字化", "raw_score": 10, "max_score": 28, "score_rate": 10 / 28},
            {"module_code": "M08", "module_name": "智能化", "raw_score": 21, "max_score": 28, "score_rate": 0.75},
            {"module_code": "M09", "module_name": "生态化", "raw_score": 19, "max_score": 25, "score_rate": 0.76},
        ],
    }
    module_blocks = "".join(
        (
            f'<div class="report-module-block"><div class="report-module-head">'
            f'{item["module_code"]} {item["module_name"]} · 得分率 {round(item["score_rate"] * 100)}%'
            f'（{item["raw_score"]}/{item["max_score"]}）</div>'
            '<table class="report-finding-table report-cad-table"><thead><tr>'
            '<th>核心结论</th><th>数据依据</th><th>分析解读</th></tr></thead><tbody>'
            f'<tr><td>{item["module_name"]}已具备一定实践基础。</td>'
            f'<td>{item["module_code"]} 合成题项得分明细用于版式验收。</td>'
            '<td>建议结合业务现场核验关键机制，并确定下一步改进动作。</td></tr>'
            '<tr><td></td><td>高分项与低分项并存。</td>'
            '<td>通过小范围试点形成可复用闭环。</td></tr></tbody></table></div>'
        )
        for item in summary["dimensions"]
    )
    html = (
        '<article class="report-document"><section><h2>一、执行摘要</h2>'
        '<table class="report-finding-table"><thead><tr><th>序号</th><th>核心发现</th><th>证据与含义</th></tr></thead>'
        '<tbody><tr><td>1</td><td><strong>用户价值导向已有较好基础</strong></td><td>M01 得分率 71%，可作为场景选择的重要依据。</td></tr>'
        '<tr><td>2</td><td><strong>流程自动化与数字化仍有提升空间</strong></td><td>M06、M07 得分率相对较低，适合优先验证高频流程。</td></tr></tbody></table></section>'
        '<section><h2>二、能力成熟度分析</h2><p class="report-section-note">以下按模块逐项分析（含该模块题目得分明细），与上方雷达图、得分排行一一对应。</p>'
        f'<div class="report-module-tables">{module_blocks}</div></section>'
        '<section><h2>三、关键矛盾与核心诊断</h2>'
        '<table class="report-finding-table report-contradiction-table"><thead><tr><th>关键矛盾</th><th>证据</th><th>诊断</th></tr></thead>'
        '<tbody><tr><td>客户导向较强与执行基础不均衡</td><td>M01 得分率 71%，但自动化和数字化得分率约 33%-36%。</td><td>需要把清晰的客户目标转化为可复制的流程与数据闭环。</td></tr>'
        '<tr><td>场景机会较多与优先级机制不足</td><td>多个部门均提出 AI 需求，但缺少统一价值指标。</td><td>先用共同指标筛选少数试点，避免资源分散。</td></tr></tbody></table></section>'
        '<section><h2>四、工作坊议题地图</h2>'
        '<table class="report-finding-table report-workshop-table"><thead><tr><th>优先级</th><th>议题</th><th>现场核心问题</th><th>必须产出</th><th>性质</th></tr></thead>'
        '<tbody><tr><td>P0</td><td>优先场景筛选</td><td>哪个场景最值得优先验证？</td><td>试点场景与指标清单</td><td>必须形成选择</td></tr></tbody></table></section>'
        '<section><h2>五、优先 AI 场景建议</h2><p class="report-section-note">旧版说明将由共享渲染契约替换。</p>'
        '<section class="report-case"><h4>智能派单与区域运力调度优化</h4><p>基于历史订单、位置、技能标签和用户偏好进行需求预测与多目标优化。</p><p><strong>预期收益：</strong>降低通勤与空驶时间，提高履约准时率。</p></section>'
        '<section class="report-case"><h4>智能客服与订单履约 Agent</h4><p>统一处理高频咨询、订单异常识别和协同跟进。</p><p><strong>预期收益：</strong>缩短响应时间并提升问题闭环效率。</p></section></section>'
        '</article>'
    )
    return SimpleNamespace(
        id=7,
        title="示例科技集团有限公司 AI 原生转型诊断报告",
        created_at=datetime(2026, 8, 23),
        summary_json=json.dumps(summary, ensure_ascii=False),
        html_content=html,
    )


def _find_report(company: str | None, report_id: int | None) -> tuple[Any | None, str | None]:
    """按公司名/报告 id 查询最近一份报告，返回 (report, company_name)。"""
    # fixture 模式不会执行本函数，也不会创建数据库 Session。数据库相关
    # import 刻意放在此处，确保 `--fixture` 是完全独立的本地视觉验收路径。
    from app.db.database import SessionLocal
    from app.models.lead import CompanyLead
    from app.models.report import Report

    db = SessionLocal()
    try:
        if report_id is not None:
            report = db.query(Report).filter(Report.id == report_id).first()
        else:
            report = (
                db.query(Report)
                .join(Report.submission)
                .join(CompanyLead)
                .filter(CompanyLead.company_name.contains(company or ""))
                .order_by(Report.id.desc())
                .first()
            )
        if not report:
            return None, None
        lead = report.submission.lead
        return report, (lead.company_name or "").strip() or None
    finally:
        db.close()


def _convert_to_pdf(docx_path: Path) -> Path | None:
    try:
        pdf_bytes = convert_customer_docx_to_pdf(docx_path.read_bytes())
        validate_report_pdf_bytes(pdf_bytes)
    except RuntimeError as exc:
        print(f"跳过 PDF 转换：{exc}")
        return None
    pdf_path = docx_path.with_suffix(".pdf")
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def _render_browser_preview(report: Any, output_stem: Path) -> tuple[Path, Path]:
    """生成独立 Chromium 视觉预览；该产物不进入客户邮件链路。"""
    html_bytes = render_report_html_attachment(report)
    html_path = output_stem.with_name(f"{output_stem.name}-browser-preview.html")
    html_path.write_bytes(html_bytes)
    pdf_bytes = render_report_pdf_bytes_with_browser_html(html_bytes)
    validate_report_pdf_bytes(pdf_bytes)
    pdf_path = output_stem.with_name(f"{output_stem.name}-browser-preview.pdf")
    pdf_path.write_bytes(pdf_bytes)
    return html_path, pdf_path


def _print_manual_hints(docx_path: Path) -> None:
    print()
    print("本机未安装 LibreOffice，可用以下任一方式把 DOCX 转成 PDF 做视觉对比：")
    print("  1) 用 Microsoft Word 打开 DOCX，另存为 PDF（与内部 Word 同源排版）。")
    print("  2) 安装 LibreOffice 后重跑本脚本自动转换：")
    print("       winget install TheDocumentFoundation.LibreOffice")
    print("  3) 或构建后端镜像后在容器内转换（镜像名以 docker images 实际为准）：")
    print("       docker compose build backend")
    print(
        f'       docker run --rm -v "{docx_path.parent.as_posix()}:/work" '
        f'<backend镜像名> libreoffice --headless --convert-to pdf:writer_pdf_Export '
        f'--outdir /work /work/{docx_path.name}'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="本地生成客户版报告 DOCX 与 PDF（视觉对比用）")
    parser.add_argument("report_id", nargs="?", type=int, help="报告 id")
    parser.add_argument("--company", help="按公司名匹配最近一份报告")
    parser.add_argument("--fixture", action="store_true", help="使用内置示例数据，不连数据库")
    parser.add_argument(
        "--browser-preview",
        action="store_true",
        help="额外生成 Chromium HTML/PDF 预览（绝不会作为邮件附件）",
    )
    parser.add_argument("--outdir", default=str(OUTPUT_DIR), help="输出目录（默认 backend/output）")
    args = parser.parse_args()

    if args.fixture:
        report, company_name = _fixture_report(), "示例科技集团有限公司"
    elif args.report_id or args.company:
        try:
            report, company_name = _find_report(args.company, args.report_id)
        except Exception as exc:  # noqa: BLE001
            print(f"读取数据库失败：{exc}")
            print("请确认 backend/.env 的 DATABASE_URL 指向目标环境，或使用 --fixture 查看示例效果。")
            return
        if not report:
            print(f"未找到匹配报告（id={args.report_id or '-'} company={args.company or '-'}）")
            return
        if not company_name:
            company_name = "企业"
    else:
        parser.print_help()
        return

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    safe_name = REPORT_FILENAME_INVALID_CHARS_RE.sub("_", company_name).strip(" ._") or "企业"
    docx_path = outdir / f"{safe_name}_AI诊断报告.docx"
    docx_path.write_bytes(generate_customer_report_docx(report, company_name))
    print(f"已生成客户版 DOCX：{docx_path}")
    print(f"  报告编号 RPT-{report.id:06d}，html_content 长度 {len(report.html_content or '')}")

    if args.browser_preview:
        try:
            html_path, preview_pdf_path = _render_browser_preview(report, docx_path.with_suffix(""))
        except RuntimeError as exc:
            print(f"Chromium 预览生成失败：{exc}")
            raise SystemExit(1) from exc
        print(f"已生成 Chromium 预览 HTML（非邮件附件）：{html_path}")
        print(f"已生成 Chromium 预览 PDF（非邮件附件）：{preview_pdf_path}")

    pdf_path = _convert_to_pdf(docx_path)
    if pdf_path:
        print(f"已转换客户版 PDF：{pdf_path}")
    else:
        _print_manual_hints(docx_path)


if __name__ == "__main__":
    main()

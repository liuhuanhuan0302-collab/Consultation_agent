"""本地生成客户版报告 DOCX 与 PDF（视觉对比用，不发送邮件）。

用法（在 backend 目录下执行）：
    python scripts/generate_customer_report.py --company 奥飞     # 按公司名匹配最近一份报告（连数据库）
    python scripts/generate_customer_report.py 7                  # 按报告 id（连数据库）
    python scripts/generate_customer_report.py --fixture          # 内置示例数据，无需数据库

输出到 backend/output/：
    {公司}_AI诊断报告.docx —— 与内部 Word 第三部分共用同一套排版组件的客户版
    {公司}_AI诊断报告.pdf  —— 本机装有 LibreOffice 时自动转换；未安装时打印转换命令
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
    validate_report_pdf_bytes,
)

OUTPUT_DIR = BACKEND_ROOT / "output"


def _fixture_report() -> SimpleNamespace:
    """内置示例数据：报告 id 与评分采用用户提供的奥飞娱乐示例值。"""
    summary = {
        "score": {"total": 106, "max_score": 242, "score_rate": 106 / 242},
        "dimensions": [
            {"module_code": "M01", "module_name": "以用户/客户为中心", "score_rate": 0.25},
            {"module_code": "M02", "module_name": "简化业务", "score_rate": 0.61},
            {"module_code": "M03", "module_name": "流程化", "score_rate": 0.58},
            {"module_code": "M04", "module_name": "数字化", "score_rate": 0.32},
            {"module_code": "M05", "module_name": "智能化", "score_rate": 0.44},
            {"module_code": "M06", "module_name": "数据驱动", "score_rate": 0.37},
            {"module_code": "M07", "module_name": "组织协同", "score_rate": 0.52},
            {"module_code": "M08", "module_name": "人才与技能", "score_rate": 0.48},
            {"module_code": "M09", "module_name": "创新文化", "score_rate": 0.41},
        ],
    }
    html = (
        "<h2>一、执行摘要</h2><p>奥飞娱乐整体 AI 原生转型成熟度处于起步阶段，"
        "得分率 44%，距离全面转型仍有较大差距。短期应聚焦少数高价值场景完成试点闭环。</p>"
        '<table class="report-finding-table"><thead><tr><th>序号</th><th>核心发现</th><th>证据与含义</th></tr></thead>'
        "<tbody><tr><td>1</td><td><strong>流程与数据基础薄弱</strong></td><td>流程化、数字化得分率低于 40%</td></tr>"
        "<tr><td>2</td><td><strong>业务场景试点不足</strong></td><td>已识别场景未形成规模化复制</td></tr></tbody></table>"
        "<h2>二、能力成熟度分析</h2><p>九大维度逐项分析如下。</p>"
        '<table class="report-finding-table report-cad-table"><thead><tr><th>核心结论</th><th>数据依据</th><th>分析解读</th></tr></thead>'
        "<tbody><tr><td>整体起步，需优先补齐基础。</td><td>9 个维度中 6 个低于 50%</td><td>先试点后推广，避免全面铺开。</td></tr>"
        "<tr><td></td><td>以用户/客户为中心得分率仅 25%</td><td>客户旅程未数字化，体验管理缺失。</td></tr></tbody></table>"
        "<h2>三、关键矛盾与核心诊断</h2>"
        '<table class="report-contradiction-table"><thead><tr><th>矛盾</th><th>表现</th><th>根因</th></tr></thead>'
        "<tbody><tr><td>转型意愿与基础能力错配</td><td>高层期待高，一线数字化工具少</td><td>缺少统一数据底座与流程标准</td></tr></tbody></table>"
        "<h2>四、工作坊议题地图</h2>"
        '<table class="report-workshop-table"><thead><tr><th>优先级</th><th>议题</th><th>讨论焦点</th><th>目标产出</th><th>时长</th></tr></thead>'
        "<tbody><tr><td>P0</td><td>优先场景筛选</td><td>试点场景与指标</td><td>场景清单</td><td>2 小时</td></tr></tbody></table>"
        "<h2>五、优先 AI 场景与案例</h2><p>优先在内容生成与客户服务环节落地 AI 场景。</p>"
        "<h2>六、管理层行动建议</h2><ol><li>成立 AI 转型专项小组</li><li>选定 1-2 个场景完成试点闭环</li><li>建立数据治理基线</li></ol>"
    )
    return SimpleNamespace(
        id=7,
        title="奥飞娱乐 AI 原生转型诊断报告",
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
    parser.add_argument("--outdir", default=str(OUTPUT_DIR), help="输出目录（默认 backend/output）")
    args = parser.parse_args()

    if args.fixture:
        report, company_name = _fixture_report(), "奥飞娱乐"
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

    pdf_path = _convert_to_pdf(docx_path)
    if pdf_path:
        print(f"已转换客户版 PDF：{pdf_path}")
    else:
        _print_manual_hints(docx_path)


if __name__ == "__main__":
    main()

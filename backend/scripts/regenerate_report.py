"""重新生成诊断报告（默认三栏格式：核心结论 | 数据依据 | 分析解读）。

用法（在 backend 目录下执行，需 PYTHONPATH 指向 backend）：
    python scripts/regenerate_report.py 241            # 按报告 id 重生成
    python scripts/regenerate_report.py --company 奥飞  # 按公司名匹配最近一份报告
    python scripts/regenerate_report.py --all           # 重生成全部 generated 报告

重生成会调用 DeepSeek 重新生成报告正文并覆盖存储的 html_content，
用于把历史报告升级为新的三栏格式。
"""
import argparse
import asyncio
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.database import SessionLocal
from app.models import Report, ReportStatus
from app.service.reporting import regenerate_report_content_for_testing


def _verify(html: str) -> dict[str, bool]:
    checks = {
        "三栏表头-核心结论": "核心结论" in html,
        "三栏表头-数据依据": "数据依据" in html,
        "三栏表头-分析解读": "分析解读" in html,
        "旧段落格式已不出现(module-body)": "report-module-body" not in html,
    }
    return checks


async def regenerate(report: Report) -> bool:
    print(f"regenerating report id={report.id} title={report.title} ...")
    print(f"  before: status={report.status} html_len={len(report.html_content or '')}")
    try:
        await regenerate_report_content_for_testing(report)
        print(f"  after:  status={report.status} html_len={len(report.html_content or '')}")
        print(f"  model: {report.model_name} error: {report.generation_error}")
        for name, ok in _verify(report.html_content or "").items():
            print(("  PASS " if ok else "  FAIL ") + name)
        return report.status == ReportStatus.generated.value
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL regenerate: {exc}")
        return False


async def main() -> None:
    parser = argparse.ArgumentParser(description="重生成诊断报告（三栏格式）")
    parser.add_argument("report_id", nargs="?", type=int, help="报告 id")
    parser.add_argument("--company", help="按公司名匹配最近一份报告")
    parser.add_argument("--all", action="store_true", help="重生成全部 generated 报告")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.all:
            reports = (
                db.query(Report)
                .filter(Report.status == ReportStatus.generated.value)
                .order_by(Report.id.asc())
                .all()
            )
            print(f"found {len(reports)} generated reports")
            ok = 0
            for report in reports:
                if await regenerate(report):
                    ok += 1
            print(f"done: {ok}/{len(reports)} regenerated successfully")
        elif args.company:
            from app.models import CompanyLead

            report = (
                db.query(Report)
                .join(Report.submission)
                .join(CompanyLead)
                .filter(CompanyLead.company_name.contains(args.company))
                .order_by(Report.id.desc())
                .first()
            )
            if not report:
                print(f"no report found for company containing '{args.company}'")
                return
            await regenerate(report)
        elif args.report_id:
            report = db.query(Report).filter(Report.id == args.report_id).first()
            if not report:
                print(f"report {args.report_id} not found")
                return
            await regenerate(report)
        else:
            parser.print_help()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

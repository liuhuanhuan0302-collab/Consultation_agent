"""Generate one reference-style module page for fast visual review."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parent))

from app.service.organization_report_service import render_organization_report_html
from app.service.pdf_service import render_report_pdf_bytes_with_browser_html
from generate_organization_report_preview import build_preview_payload


REFERENCE_QUESTIONS = [
    ("用户研究与洞察机制", 2.00),
    ("洞察传达决策速度", 2.25),
    ("流程以用户为原点", 2.13),
    ("用户满意度/NPS权重", 0.88),
    ("用户需求冲突处理", 2.00),
    ("用户数据战略资产", 1.63),
    ("AI辅助用户洞察", 0.50),
]

REFERENCE_SIGNALS = {
    "洞察传达决策速度": "传统依赖经销商与海外KA渠道的商业模式，形成了信息屏障",
    "流程以用户为原点": "现有流程基本上是以内部门效率视角而非用户视角",
    "用户研究与洞察机制": "用户洞察依赖人工，评论区靠产品企划手搓归类，IP选品靠设计师个人经验，缺乏直连C端消费者的实时数据闭环；前置用户验证不是标准流程，产品上市后才发现不符合预期，靠降价消化库存",
    "用户需求冲突处理": "一线响应用户速度慢，用户需求与内部规则冲突时需层层审批",
    "用户数据战略资产": "0-30+用户资产割裂、缺失，各BU用户互不打通，跨业务用户数据资产流转复用价值为零",
    "用户满意度/NPS权重": "用户价值导向激励机制基本缺失，用户满意度/NPS指标在绩效考核中的权重较低，多数受访者该项为0分",
    "AI辅助用户洞察": "AI辅助用户洞察处于有尝试未成体系阶段，未系统落地",
}


def _risk_level(score: float) -> str:
    if score < 1:
        return "高风险"
    if score < 2.1:
        return "较弱"
    if score < 3.1:
        return "良好"
    return "优秀"


def _reference_payload():
    payload, analysis = build_preview_payload()
    module = payload.data["modules"][0]
    module["module_name"] = "一心 — 以用户/客户为中心"
    module["questions"] = [
        {
            **question,
            "short_title": title,
            "answer_value": score,
            "score_out_of_4": score,
            "score_rate": score / 4,
            "risk_level": _risk_level(score),
        }
        for question, (title, score) in zip(module["questions"], REFERENCE_QUESTIONS)
    ]
    module["raw_score"] = sum(score for _title, score in REFERENCE_QUESTIONS)
    module["score_rate"] = module["raw_score"] / module["max_score"]
    module["risk_level"] = _risk_level(module["raw_score"] / len(REFERENCE_QUESTIONS))
    payload.data["company"]["company_name"] = "示例企业有限公司"
    payload.data["company"]["research"] = (
        "【视觉演示用合成背景】企业业务依赖经销商与海外KA渠道，产品团队主要通过渠道、项目和内部人员经验接收用户反馈；"
        "各业务线用户数据尚未完全打通，AI辅助洞察处于试点阶段。"
    )
    analysis["modules"][0]["question_interpretations"] = [
        {
            "question_code": question["question_code"],
            "signal": REFERENCE_SIGNALS[question["short_title"]],
        }
        for question in module["questions"]
    ]
    analysis["modules"][0]["emphasis_question_codes"] = ["Q01", "Q02", "Q03", "Q06"]
    analysis["modules"][0]["core_diagnosis"] = (
        "企业当前的用户洞察仍主要依赖渠道和内部经验，终端用户反馈尚未稳定进入产品决策。"
        "这使得不同业务线难以共享用户资产，用户需求与产品动作之间存在较长的信息链路。"
    )
    analysis["modules"][0]["root_cause"] = (
        "用户信息从渠道、项目到产品团队的传递缺少统一机制，数据资产、责任边界与用户价值导向尚未形成闭环。"
    )
    return payload, analysis


def main() -> None:
    payload, analysis = _reference_payload()
    html = render_organization_report_html(payload, {"modules": [analysis["modules"][0]]}, version=1)
    insight_marker = '<section class="page module-insight-page">'
    marker_index = html.find(insight_marker)
    if marker_index < 0:
        raise RuntimeError("未找到模块分析页边界")
    html = html[:marker_index] + "</body></html>"
    html = html.replace(
        "</style>",
        """
/* single-page reference tuning */
.title-wrap h2 { font-size:30px; }
.module-meta { font-size:16px; }
.title-wrap p { font-size:10.5px; }
.module-score-grid { grid-template-columns:31% 63%; column-gap:3%; height:132mm; }
.chart-panel svg { height:124mm; }
table { font-size:13px; }
th { font-size:14px; padding:8px 10px; text-align:center !important; }
td { font-size:12.5px; line-height:1.42; padding:7px 9px; }
th:nth-child(1) { width:24%; }
th:nth-child(2) { width:13%; }
th:nth-child(3) { width:16%; }
th:nth-child(4) { width:47%; }
.score-cell { font-size:15px; }
.risk { font-size:11.5px; padding:3px 7px; }
.signal-text { font-size:12px; line-height:1.5; }
.signal-emphasis { color:#4e3bc2; font-weight:800; }
.score-legend { font-size:11px; left:34%; right:4%; bottom:2mm; }
</style>""",
        1,
    )
    output = (
        Path(__file__).resolve().parents[2]
        / "output"
        / "pdf"
        / "organization-diagnosis-single-page-reference-final.pdf"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(render_report_pdf_bytes_with_browser_html(html.encode("utf-8")))
    print(f"generated {output} (single module page)")


if __name__ == "__main__":
    main()

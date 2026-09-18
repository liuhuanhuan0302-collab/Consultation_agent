"""Generate a local, anonymized visual preview of the organization report PDF."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.service.organization_report_service import (
    OrganizationReportPayload,
    _default_signal,
    render_organization_report_html,
)
from app.service.pdf_service import render_report_pdf_bytes_with_browser_html


MODULE_NAMES = [
    "一心·用户/客户为中心",
    "二简·简化业务",
    "三敏·敏捷组织",
    "四能·能力建设",
    "五化·生态协同",
    "六数·数据资产",
    "七智·智能应用",
    "八链·流程协同",
    "九治·治理机制",
]
QUESTION_COUNTS = [7, 7, 7, 7, 7, 7, 7, 6, 6]
QUESTION_TITLES = ["用户洞察机制", "流程响应速度", "决策标准", "协同机制", "数据资产", "智能应用", "持续改进"]


def _contextual_signal(question: dict) -> str:
    """Synthetic preview copy showing how enterprise context changes a signal."""

    title = question["short_title"]
    score = int(question["score_out_of_4"])
    signals = {
        "用户洞察机制": {
            3: "示例企业已有客户反馈基础，但一线用户信息仍多由销售与项目团队转述，需核验洞察是否稳定进入产品决策。",
            2: "企业当前以渠道合作和企业客户项目为主，用户反馈沿渠道和项目链路传递，尚未形成稳定的用户研究闭环。",
            1: "企业依赖渠道获取客户信息，部门缺少直接触达终端用户的机制，容易出现产品上线后才发现需求偏差。",
        },
        "流程响应速度": {
            3: "多业务线和项目交付并行时，现有流程基本能支撑响应；需核验跨部门交接是否仍保持统一时限。",
            2: "企业业务同时包含渠道合作与项目交付，流程虽能运行但偏内部效率视角，跨部门等待可能拖慢用户需求响应。",
            1: "项目制交付与多业务线并行放大了流程等待，需求容易在审批和部门交接中积压，需明确时限与升级路径。",
        },
        "决策标准": {
            3: "已有一定决策依据，但在多业务线场景下仍需核验关键事项是否采用统一口径，并能被不同团队复用。",
            2: "当前决策更多依赖项目经验，面对不同客户和业务线时容易出现口径差异，需补充规则、记录与复盘。",
            1: "决策标准较弱，渠道、项目与产品之间可能各自判断，需优先明确授权边界和关键事项的留痕机制。",
        },
        "协同机制": {
            3: "协同已有基础，但需结合渠道、项目和产品之间的信息流转，核验责任边界与交付验收是否清晰。",
            2: "业务链路较长，部门间协同仍可能依赖人工转述，建议检查需求交接、信息同步和问题升级是否形成闭环。",
            1: "渠道合作与项目交付叠加后，需求流转容易依赖临时沟通，存在等待、返工和责任边界模糊风险。",
        },
        "数据资产": {
            3: "已有一定客户和项目数据沉淀，但需核验数据口径、更新责任和跨业务线复用是否真正稳定。",
            2: "客户、项目和产品数据已有积累但尚未充分打通，建议重点核验统一口径、共享权限和实际使用频率。",
            1: "各业务线数据可能存在割裂，部门难以用同一份数据判断客户和项目状态，需优先补齐数据责任与共享机制。",
        },
        "智能应用": {
            3: "已有智能应用尝试，但需结合企业现有项目和客户服务流程，核验是否形成稳定场景、责任人和效果评估。",
            2: "AI应用已开始试点，但尚未充分嵌入渠道、项目和产品流程，需核验真实使用频率及反馈闭环。",
            1: "智能应用仍处于零散尝试阶段，尚未稳定转化为部门动作，需先明确使用场景、责任边界和可验证产出。",
        },
        "持续改进": {
            3: "已有改进动作，但在多业务线和项目交付场景下，仍需核验问题是否有统一记录、责任跟踪和效果验证。",
            2: "部门具备一定改进意识，但跨团队问题容易在项目结束后失去追踪，建议检查复盘是否沉淀为可复用机制。",
            1: "问题改进较依赖临时推动，渠道、项目与产品之间的经验难以沉淀，存在同类问题反复发生的风险。",
        },
    }
    return signals.get(title, {}).get(score, _default_signal(question))


def build_preview_payload() -> tuple[OrganizationReportPayload, dict]:
    modules: list[dict] = []
    question_texts: dict[str, str] = {}
    question_index = 1
    for module_index, (module_name, question_count) in enumerate(zip(MODULE_NAMES, QUESTION_COUNTS), start=1):
        questions: list[dict] = []
        answers: list[int] = []
        for offset in range(question_count):
            question_code = f"Q{question_index:02d}"
            answer = [3, 2, 2, 1, 3, 1, 2][(question_index - 1) % 7]
            title = QUESTION_TITLES[offset]
            question_texts[question_code] = f"{module_name}：{title}是否已经形成稳定机制？"
            questions.append(
                {
                    "question_id": question_index,
                    "question_code": question_code,
                    "short_title": title,
                    "answer_value": answer,
                    "max_score": 4,
                    "score_rate": answer / 4,
                    "score_out_of_4": answer,
                    "risk_level": "优秀" if answer >= 3 else ("良好" if answer >= 2 else ("较弱" if answer >= 1 else "高风险")),
                }
            )
            answers.append(answer)
            question_index += 1
        max_score = question_count * 4
        raw_score = sum(answers)
        rate = raw_score / max_score
        modules.append(
            {
                "module_code": f"M{module_index:02d}",
                "module_name": module_name,
                "module_max_score": max_score,
                "raw_score": raw_score,
                "max_score": max_score,
                "score_rate": rate,
                "risk_level": "优秀" if rate >= 0.75 else ("良好" if rate >= 0.5 else ("较弱" if rate >= 0.25 else "高风险")),
                "questions": questions,
            }
        )

    total = sum(module["raw_score"] for module in modules)
    maximum = sum(module["max_score"] for module in modules)
    data = {
        "report_format_version": 1,
        "company": {
            "company_name": "示例科技有限公司",
            "industry": "软件服务",
            "company_size": "中型企业",
            "city": "广州",
            "research": "【视觉演示用合成背景】示例企业是一家面向企业客户的软件服务公司，业务依赖渠道合作与项目交付；产品团队接收用户反馈主要来自销售、项目和客户成功团队；客户、项目与产品数据仍在整合，AI应用处于试点阶段。",
        },
        "organization": {
            "respondent_name": "张三",
            "department": "产品与研发部",
            "position": "部门负责人",
            "submitted_at": "2026-09-14T15:30:00",
        },
        "score": {
            "total": total,
            "max_score": maximum,
            "score_rate": total / maximum,
            "risk_level": "良好",
            "average_out_of_4": 2.1,
        },
        "modules": modules,
        "enterprise_report_id": 1001,
    }
    analysis = {
        "modules": [
            {
                "module_code": module["module_code"],
                "core_diagnosis": f"{module['module_name']}整体处于{module['risk_level']}水平，基础能力已经显现，但题项表现并不均衡。低分题显示机制落地和日常执行仍有提升空间。",
                "root_cause": "当前答卷反映出制度、流程与日常执行之间仍存在衔接空档，需结合内部资料进一步确认根因。",
                "question_interpretations": [
                    {"question_code": question["question_code"], "signal": _contextual_signal(question)}
                    for question in module["questions"]
                ],
            }
            for module in modules
        ],
        "overall_core_diagnosis": [
            "部门能力表现存在题项差异，低分项应作为内部核验和改进的优先入口。",
            "固定评分显示基础机制已经形成，但跨流程协同和持续执行仍需加强。",
        ],
        "overall_root_cause": "从当前答卷看，主要问题更可能位于机制标准化、执行闭环和数据反馈之间的连接，而非单一岗位能力不足；具体原因仍需结合企业内部资料核验。",
        "recommendations": [
            "优先梳理低分题对应的流程、责任人和可验证产出。",
            "建立部门内定期复盘机制，用数据跟踪改进是否持续发生。",
            "将跨部门协同事项明确为可追踪的任务和交付节点。",
        ],
    }
    return OrganizationReportPayload(data, question_texts, enterprise_report_id=1001), analysis


def main() -> None:
    payload, analysis = build_preview_payload()
    html = render_organization_report_html(payload, analysis, version=1)
    output = Path(__file__).resolve().parents[2] / "output" / "pdf" / "organization-diagnosis-v6-context-preview.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(render_report_pdf_bytes_with_browser_html(html.encode("utf-8")))
    print(f"generated {output} ({len(payload.question_texts)} questions, {len(payload.data['modules'])} modules)")


if __name__ == "__main__":
    main()

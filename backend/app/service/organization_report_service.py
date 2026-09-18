"""Independent organization-diagnosis scoring, AI analysis and PDF workflow."""

from __future__ import annotations

import asyncio
import base64
import html as html_lib
import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    OrganizationAnalysisStatus,
    OrganizationReport,
    OrganizationReportStatus,
    OrganizationReportTask,
    OrganizationReportTaskKind,
    OrganizationReportTaskStatus,
    OrganizationSubmission,
    OrganizationSubmissionStatus,
)
from app.repositories import organization_report_repo
from app.repositories.questionnaire_repo import active_modules_with_questions
from app.service.api_gateway_service import effective_llm_override
from app.service.company_research import validate_structured_research
from app.service.pdf_service import render_report_pdf_bytes_with_browser_html
from app.service.scoring import ModuleScoreSpec, QuestionScoreSpec, compute_scores
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

ORGANIZATION_REPORT_FORMAT_VERSION = 1
MAX_AI_ATTEMPTS = 3


class OrganizationReportError(RuntimeError):
    """Base error for the independent organization report workflow."""


class OrganizationReportNotEligibleError(OrganizationReportError):
    pass


class OrganizationReportConflictError(OrganizationReportError):
    pass


class OrganizationReportContentError(OrganizationReportError):
    pass


@dataclass(frozen=True)
class OrganizationReportPayload:
    """Current DB-derived data used for one analysis attempt."""

    data: dict[str, Any]
    question_texts: dict[str, str]
    enterprise_report_id: int


def _load_valid_enterprise_report(db: Session, company_name: str):
    for report in organization_report_repo.list_enterprise_report_candidates(db, company_name):
        try:
            research = json.loads(report.company_research_json or "")
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(research, dict) and not validate_structured_research(research):
            return report, research
    return None, None


def _research_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        pieces: list[str] = []
        for item in value:
            if isinstance(item, dict):
                title = str(item.get("title") or "").strip()
                content = str(item.get("content") or "").strip()
                if title and content:
                    pieces.append(f"{title}：{content}")
                elif content:
                    pieces.append(content)
            elif item:
                pieces.append(str(item).strip())
        return "；".join(piece for piece in pieces if piece)
    return str(value or "").strip()


def _company_context(enterprise_report, research: dict[str, Any]) -> dict[str, str]:
    lead = enterprise_report.submission.lead
    allowed_sections = (
        ("company_overview", "公司介绍"),
        ("revenue_scale", "规模信息"),
        ("products", "产品与业务"),
        ("industry_characteristics", "行业特点"),
        ("development_status", "发展现状"),
    )
    return {
        "company_name": str(lead.company_name or "").strip(),
        "industry": str(lead.industry or "").strip(),
        "company_size": str(lead.company_size or "").strip(),
        "city": str(lead.city or "").strip(),
        "research": "；".join(
            f"{label}：{_research_text(research.get(key))[:360]}"
            for key, label in allowed_sections
            if _research_text(research.get(key))
        ),
    }


def _short_title(text: str, dimension: str | None = None) -> str:
    """Create a stable compact title for the visual report table and radar."""

    value = (dimension or text or "").strip()
    value = re.sub(r"^(是否|请问|贵公司|公司|企业|您是否)\s*", "", value)
    value = re.sub(r"[（(][^）)]*[）)]", "", value)
    value = value.rstrip("？?。；;")
    value = re.sub(r"\s+", "", value)
    return value[:18] + ("…" if len(value) > 18 else "")


def _risk_level(score_rate: float) -> str:
    if score_rate < 0.25:
        return "高风险"
    if score_rate < 0.5:
        return "较弱"
    if score_rate < 0.75:
        return "良好"
    return "优秀"


def build_current_payload(db: Session, submission: OrganizationSubmission) -> OrganizationReportPayload:
    enterprise_report, research = _load_valid_enterprise_report(db, submission.company_name)
    if enterprise_report is None or research is None:
        raise OrganizationReportNotEligibleError("该企业暂无有效的企业诊断报告，暂不可生成组织分析")

    modules = active_modules_with_questions(db)
    questions = [
        question
        for module in modules
        for question in sorted(module.questions, key=lambda item: (item.sort_order, item.code))
        if question.is_active
    ]
    answer_map = organization_report_repo.get_answer_map(db, submission.id)
    question_ids = {question.id for question in questions}
    missing = sorted(question_id for question_id in question_ids if question_id not in answer_map)
    if missing:
        raise OrganizationReportContentError(f"当前题库有 {len(missing)} 道题缺少答案，无法生成组织报告")

    score_result = compute_scores(
        [ModuleScoreSpec(module.id, module.code, module.name, module.max_score) for module in modules],
        [QuestionScoreSpec(question.id, question.module_id, question.max_score) for question in questions],
        answer_map,
    )
    dimension_map = {dimension.module_id: dimension for dimension in score_result.dimensions}
    module_payloads: list[dict[str, Any]] = []
    question_texts: dict[str, str] = {}
    for module in modules:
        dimension = dimension_map[module.id]
        module_questions: list[dict[str, Any]] = []
        for question in sorted(module.questions, key=lambda item: (item.sort_order, item.code)):
            if not question.is_active:
                continue
            answer_value = answer_map[question.id]
            score_rate = answer_value / question.max_score if question.max_score else 0
            code = str(question.code)
            short_title = _short_title(question.text, question.dimension)
            question_texts[code] = question.text
            module_questions.append(
                {
                    "question_id": question.id,
                    "question_code": code,
                    "short_title": short_title,
                    "answer_value": answer_value,
                    "max_score": question.max_score,
                    "score_rate": round(score_rate, 4),
                    "score_out_of_4": round(score_rate * 4, 2),
                    "risk_level": _risk_level(score_rate),
                }
            )
        module_payloads.append(
            {
                "module_code": module.code,
                "module_name": module.name,
                "module_max_score": module.max_score,
                "raw_score": dimension.raw_score,
                "max_score": dimension.max_score,
                "score_rate": dimension.score_rate,
                "risk_level": dimension.risk_level,
                "questions": module_questions,
            }
        )

    company = _company_context(enterprise_report, research)
    payload = {
        "report_format_version": ORGANIZATION_REPORT_FORMAT_VERSION,
        "company": company,
        "organization": {
            "respondent_name": submission.respondent_name,
            "department": submission.department,
            "position": submission.position,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        },
        "score": {
            "total": score_result.total_score,
            "max_score": score_result.max_score,
            "score_rate": score_result.score_rate,
            "risk_level": score_result.risk_level,
            "average_out_of_4": round(
                sum(item["answer_value"] for item in (question for module in module_payloads for question in module["questions"]))
                / len(questions),
                2,
            ) if questions else 0,
        },
        "modules": module_payloads,
        "enterprise_report_id": enterprise_report.id,
    }
    return OrganizationReportPayload(
        data=payload,
        question_texts=question_texts,
        enterprise_report_id=enterprise_report.id,
    )


def _prompt_payload(payload: OrganizationReportPayload) -> dict[str, Any]:
    data = json.loads(json.dumps(payload.data, ensure_ascii=False))
    # The respondent identity is displayed in the administrator-only PDF but
    # is not needed by the model to interpret department-level answers.
    data["organization"].pop("respondent_name", None)
    # The model receives the full current question text, while persisted report
    # metadata keeps only IDs/scores and the final rendered output.
    for module in data["modules"]:
        for question in module["questions"]:
            question["question_text"] = payload.question_texts.get(question["question_code"], "")
    return data


def build_organization_prompt(payload: OrganizationReportPayload, validation_feedback: list[str] | None = None) -> str:
    feedback = ""
    if validation_feedback:
        feedback = "\n上一次输出未通过校验，请修正：\n- " + "\n- ".join(validation_feedback)
    return f"""
你是一名严谨的组织诊断顾问。请分析一个企业内部“{payload.data['organization']['department']}”部门负责人的组织诊断答卷。
{feedback}

企业信息用于背景交叉分析；所有部门层面的核心判断必须来自本部门答卷和固定评分。可以说明“该企业的业务模式/客户来源/数据结构使这一题更值得关注”，但不得把企业公开信息直接写成该部门已经发生的事实，不得虚构访谈、员工原话、数据或事件。
请只输出 JSON，不要 markdown 代码块，不要解释文字，结构必须是：
{{
  "modules": [
    {{
      "module_code": "M01",
      "core_diagnosis": "该模块2-3句核心诊断，说明主要表现、题项信号及其管理含义",
      "root_cause": "该模块深层原因",
      "question_interpretations": [
        {{"question_code": "Q01", "signal": "不超过100字的信号解读"}}
      ]
    }}
  ],
  "overall_core_diagnosis": ["整体核心诊断1", "整体核心诊断2"],
  "overall_root_cause": "整体深层根因",
  "recommendations": ["针对该部门的建议1", "针对该部门的建议2"]
}}

要求：
1. modules 必须覆盖全部 {len(payload.data['modules'])} 个模块，module_code 必须一致。
2. 每个模块的 question_interpretations 必须覆盖该模块全部题目，question_code 必须一致。
3. 核心诊断请写2-3句，说明该模块的整体表现、题项差异及其管理含义；信号解读不超过100字，必须结合题目含义、实际得分和风险区间，并在有直接对应依据时结合企业背景，说明“当前部门可能处于什么状态、会带来什么管理影响、下一步核验什么”，不得只重复分数或泛泛写“建议加强”。
4. overall_core_diagnosis 输出2-4条，recommendations输出2-5条。
5. 不要生成高管访谈原声、员工引语或未经数据支持的具体事实。

诊断数据：
{json.dumps(_prompt_payload(payload), ensure_ascii=False, indent=2)}
""".strip()


async def call_organization_llm(
    db: Session,
    payload: OrganizationReportPayload,
    validation_feedback: list[str] | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    override = effective_llm_override(db)
    base_url = (override.base_url or settings.deepseek_base_url).strip()
    api_key = override.api_key or settings.deepseek_api_key
    model = override.model or settings.deepseek_model
    if override.base_url and not override.api_key:
        raise OrganizationReportError("LLM接口已配置但API Key无法解密，请在后台重新保存LLM配置")
    if not api_key:
        raise OrganizationReportError("未配置LLM API Key，无法生成组织AI解读")
    timeout = max(settings.deepseek_timeout_seconds, 120)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是严谨的组织内部诊断报告生成助手。"},
                    {"role": "user", "content": build_organization_prompt(payload, validation_feedback)},
                ],
                "temperature": 0.25,
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise OrganizationReportError("LLM未返回有效组织分析内容")
        return content, model


def _parse_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def validate_analysis(data: dict[str, Any] | None, payload: OrganizationReportPayload) -> list[str]:
    if not data:
        return ["AI未返回可解析的JSON"]
    errors: list[str] = []
    modules = data.get("modules")
    expected_modules = {module["module_code"] for module in payload.data["modules"]}
    if not isinstance(modules, list) or not modules:
        return ["缺少modules"]
    actual_modules = {str(item.get("module_code") or "") for item in modules if isinstance(item, dict)}
    missing_modules = sorted(expected_modules - actual_modules)
    if missing_modules:
        errors.append(f"模块未覆盖：{', '.join(missing_modules)}")
    for module in payload.data["modules"]:
        item = next(
            (candidate for candidate in modules if isinstance(candidate, dict) and candidate.get("module_code") == module["module_code"]),
            None,
        )
        if not item:
            continue
        for field in ("core_diagnosis", "root_cause"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{module['module_code']}缺少{field}")
        expected_questions = {question["question_code"] for question in module["questions"]}
        interpretations = item.get("question_interpretations")
        actual_questions = {
            str(question.get("question_code") or "")
            for question in interpretations
            if isinstance(question, dict)
        } if isinstance(interpretations, list) else set()
        missing_questions = sorted(expected_questions - actual_questions)
        if missing_questions:
            errors.append(f"{module['module_code']}题目未覆盖：{', '.join(missing_questions)}")
    for field in ("overall_core_diagnosis", "recommendations"):
        if not isinstance(data.get(field), list) or not data[field]:
            errors.append(f"缺少{field}")
    if not isinstance(data.get("overall_root_cause"), str) or not data["overall_root_cause"].strip():
        errors.append("缺少overall_root_cause")
    return errors


def _escape(value: Any) -> str:
    return html_lib.escape(str(value or ""))


def _compact_question_code(value: Any) -> str:
    match = re.fullmatch(r"Q0*(\d+)", str(value or ""))
    return f"Q{int(match.group(1))}" if match else str(value or "")


def _brand_logo_data_uri() -> str:
    asset = Path(__file__).resolve().parents[1] / "assets" / "brand-logo-horizontal.webp"
    try:
        return "data:image/webp;base64," + base64.b64encode(asset.read_bytes()).decode("ascii")
    except OSError:
        logger.warning("组织诊断PDF品牌Logo资源不存在：%s", asset)
        return ""


def _core_diagnosis_items(
    module: dict[str, Any],
    module_analysis: dict[str, Any],
    weak_questions: list[dict[str, Any]],
) -> list[str]:
    """Build a readable multi-point diagnosis while keeping old analyses compatible."""

    raw = module_analysis.get("core_diagnosis")
    if isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item or "").strip()]
    else:
        text = str(raw or "").strip()
        items = [text] if text else []

    questions = module.get("questions") or []
    average = sum(float(question["score_out_of_4"]) for question in questions) / max(len(questions), 1)
    risk_level = str(module.get("risk_level") or "待核验")
    if len(items) < 3:
        items.append(
            f"本模块共{len(questions)}题，模块均分{average:.2f}/4，整体处于{risk_level}区间；"
            "题项之间的差异提示，基础能力与日常执行的稳定性仍需结合内部材料核验。"
        )
    if len(items) < 3 and weak_questions:
        focus = "、".join(
            f"{_compact_question_code(question['question_code'])} {question['short_title']}（{question['score_out_of_4']:.2f}/4）"
            for question in weak_questions[:3]
        )
        items.append(
            f"相对低分项集中在{focus}，建议优先核验对应流程、责任边界、交付节点以及复盘记录，"
            "确认问题是机制缺口还是执行波动。"
        )
    if not items:
        items = ["本模块需要结合题目得分和部门内部资料进一步核验。"]
    return items[:4]


def _default_signal(question: dict[str, Any]) -> str:
    """Provide a useful, score-aware fallback for older or incomplete analyses."""

    title = str(question.get("short_title") or "该题")
    score = int(round(float(question.get("score_out_of_4") or 0)))
    signals = {
        "用户洞察机制": {
            4: "用户洞察机制较为成熟，建议继续验证洞察是否稳定进入产品决策并形成可追踪的业务闭环。",
            3: "已具备一定的用户反馈与洞察基础，但仍需核验是否持续沉淀为可复用的方法和明确产出。",
            2: "用户洞察已有零散实践，但尚未形成稳定、可复用的研究与反馈机制，决策仍可能依赖个人经验。",
            1: "用户洞察主要依赖临时收集和个人经验，缺少持续验证与沉淀机制，产品决策容易与真实需求脱节。",
            0: "尚未看到稳定的用户洞察机制，需求判断缺少持续数据和验证依据，存在方向偏移与反复返工风险。",
        },
        "流程响应速度": {
            4: "流程响应速度较好，建议继续检查跨部门事项是否保持同样的响应标准，避免规模扩大后出现瓶颈。",
            3: "流程基本能够支撑日常响应，但仍需核验跨部门交接、审批节点和异常事项是否存在延迟。",
            2: "流程能够运行但响应稳定性一般，建议重点核验等待时间、审批层级和跨部门交接是否拖慢业务推进。",
            1: "流程响应偏慢，需求可能在审批和部门交接中积压，需优先明确时限、责任人和异常升级路径。",
            0: "尚未形成有效的响应机制，需求处理容易失控或反复等待，存在直接影响交付和客户体验的风险。",
        },
        "决策标准": {
            4: "决策标准较清晰，建议继续验证关键决策是否有统一记录，并能在不同团队间稳定复用。",
            3: "已有相对明确的决策依据，但仍需核验标准是否透明、可复盘，并能减少不同人员的判断偏差。",
            2: "决策主要有经验基础，但标准化程度不足，建议检查关键事项是否缺少统一口径、记录与复盘。",
            1: "决策标准较弱，判断容易依赖个人经验和临时协调，需优先补齐规则、授权边界与留痕机制。",
            0: "缺少可执行的决策标准，重要事项难以形成一致判断，存在反复讨论、责任不清和执行偏差风险。",
        },
        "协同机制": {
            4: "部门协同机制较成熟，建议继续关注协同结果是否可追踪，并保持责任边界与交付标准清晰。",
            3: "协同基本能够完成，但仍需核验需求交接、责任边界和交付验收是否有稳定的共同规则。",
            2: "部门间已有协同动作，但较依赖人工推动，建议检查信息传递、任务交接和问题升级是否形成闭环。",
            1: "协同机制较弱，需求流转仍可能依赖临时沟通，容易出现等待、返工和责任边界模糊。",
            0: "尚未形成有效的协同机制，跨部门事项容易断点和失焦，存在持续拖延、重复劳动与交付失真的风险。",
        },
        "数据资产": {
            4: "数据资产基础较好，建议继续验证数据口径、权限和使用结果是否能够持续支撑业务决策。",
            3: "已有一定数据沉淀，但仍需核验数据质量、统一口径和实际使用频率，避免数据停留在存储层。",
            2: "数据已有积累但整合和复用不足，建议重点检查数据口径、更新责任和跨团队共享是否稳定。",
            1: "数据资产较为分散或缺少维护，业务判断可能回到经验驱动，需优先明确口径、责任和可用场景。",
            0: "尚未形成可依赖的数据资产，关键判断缺少连续数据支撑，存在信息断裂和重复采集的风险。",
        },
        "智能应用": {
            4: "智能应用已有稳定落地，建议继续验证应用效果、使用边界和风险治理是否同步完善。",
            3: "已有明确的智能应用实践，但仍需核验是否形成可复制场景、稳定流程和效果评估。",
            2: "智能应用开始进入业务，但实践仍较分散，建议检查真实使用频率、流程嵌入和效果反馈是否形成闭环。",
            1: "智能应用处于尝试阶段，尚未稳定嵌入业务流程，需优先明确使用场景、责任边界和可验证产出。",
            0: "尚未形成有效的智能应用，相关能力暂未转化为稳定的业务动作，存在投入与实际产出脱节的风险。",
        },
        "持续改进": {
            4: "持续改进机制较成熟，建议继续保持问题复盘、责任跟踪和效果验证的闭环。",
            3: "已有持续改进动作，但仍需核验改进事项是否有明确责任人、完成标准和后续效果记录。",
            2: "部门具备一定改进意识，但闭环稳定性不足，建议检查问题是否按期复盘、跟踪并验证结果。",
            1: "持续改进较依赖临时推动，问题容易重复出现，需优先建立统一的问题记录、责任跟踪和复盘机制。",
            0: "尚未形成持续改进机制，问题缺少沉淀和追踪，存在同类问题反复发生、组织经验无法积累的风险。",
        },
    }
    return signals.get(title, {}).get(
        score,
        f"{title}当前得分为{float(question.get('score_out_of_4') or 0):.2f}/4，需结合部门实际流程、责任边界和可验证产出进一步核验。",
    )


def _score_color(score_rate: float) -> str:
    if score_rate < 0.25:
        return "#c92a2a"
    if score_rate < 0.5:
        return "#c56b13"
    if score_rate < 0.75:
        return "#159570"
    return "#176b53"


def _radar_svg(module: dict[str, Any]) -> str:
    rows = module["questions"]
    width, height, cx, cy, radius = 360, 300, 180, 148, 96
    count = max(3, len(rows))
    def point(index: int, value: float) -> tuple[float, float]:
        angle = -math.pi / 2 + (2 * math.pi * index / count)
        return cx + math.cos(angle) * radius * value, cy + math.sin(angle) * radius * value
    rings = []
    for level in (0.25, 0.5, 0.75, 1):
        points = " ".join(f"{point(index, level)[0]:.1f},{point(index, level)[1]:.1f}" for index in range(count))
        rings.append(f'<polygon points="{points}" class="radar-ring" />')
    axes = []
    labels = []
    value_points = []
    baseline_points = []
    dots = []
    for index, row in enumerate(rows):
        edge_x, edge_y = point(index, 1)
        axes.append(f'<line x1="{cx}" y1="{cy}" x2="{edge_x:.1f}" y2="{edge_y:.1f}" class="radar-axis" />')
        label_x, label_y = point(index, 1.0)
        anchor = "middle"
        if label_x < cx - 16:
            anchor = "end"
        elif label_x > cx + 16:
            anchor = "start"
        labels.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" class="radar-label">'
            f'{_escape(_compact_question_code(row["question_code"]))} {_escape(row["short_title"][:4])} {row["score_out_of_4"]:.2f}</text>'
        )
        value_x, value_y = point(index, float(row["score_rate"]))
        value_points.append(f"{value_x:.1f},{value_y:.1f}")
        baseline_x, baseline_y = point(index, 0.5)
        baseline_points.append(f"{baseline_x:.1f},{baseline_y:.1f}")
        dots.append(f'<circle cx="{value_x:.1f}" cy="{value_y:.1f}" r="4.5" class="radar-point" />')
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{_escape(module["module_name"])}雷达图">'
        f'<text x="{cx}" y="18" text-anchor="middle" class="radar-scale">4</text>'
        + "".join(rings + axes)
        + f'<polygon points="{" ".join(baseline_points)}" class="radar-baseline" />'
        + f'<polygon points="{" ".join(value_points)}" class="radar-value" />'
        + "".join(dots + labels)
        + '<line x1="45" y1="278" x2="78" y2="278" class="legend-line" /><text x="87" y="282" class="legend-text">实际</text>'
        + '<line x1="190" y1="278" x2="223" y2="278" class="legend-baseline" /><text x="232" y="282" class="legend-text">基准2分</text>'
        + "</svg>"
    )


def _analysis_map(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("module_code")): item
        for item in analysis.get("modules", [])
        if isinstance(item, dict)
    }


def render_organization_report_html(payload: OrganizationReportPayload, analysis: dict[str, Any], version: int) -> str:
    data = payload.data
    modules = data["modules"]
    by_code = _analysis_map(analysis)
    company = data["company"]
    organization = data["organization"]
    logo_uri = _brand_logo_data_uri()
    module_pages: list[str] = []
    for module_index, module in enumerate(modules, start=1):
        module_analysis = by_code.get(module["module_code"], {})
        interpretation_map = {
            str(item.get("question_code")): {
                "text": str(item.get("signal") or "").strip(),
                "emphasis": bool(item.get("emphasis")),
            }
            for item in module_analysis.get("question_interpretations", [])
            if isinstance(item, dict)
        }
        emphasis_codes = {
            str(code)
            for code in module_analysis.get("emphasis_question_codes", [])
            if str(code).strip()
        }
        table_questions = sorted(
            module["questions"],
            key=lambda question: float(question["score_out_of_4"]),
            reverse=True,
        )
        rows = "".join(
            f'''<tr><td><strong>{_escape(_compact_question_code(question["question_code"]))}</strong> {_escape(question["short_title"])}</td>'''
            f'''<td class="score-cell" style="color:{_score_color(question["score_rate"])}">{question["score_out_of_4"]:.2f}</td>'''
            f'''<td><span class="risk" style="color:{_score_color(question["score_rate"])};background:{_score_color(question["score_rate"])}18">{_escape(question["risk_level"])}</span></td>'''
            f'''<td class="signal-text{' signal-emphasis' if interpretation_map.get(question["question_code"], {}).get("emphasis") or question["question_code"] in emphasis_codes else ''}">{_escape((interpretation_map.get(question["question_code"]) or {}).get("text") or _default_signal(question))}</td></tr>'''
            for question in table_questions
        )
        root_cause = module_analysis.get("root_cause") or "当前数据不足以支持更具体的根因判断。"
        module_average = (
            sum(question["score_out_of_4"] for question in module["questions"])
            / max(len(module["questions"]), 1)
        )
        first_code = module["questions"][0]["question_code"] if module["questions"] else ""
        last_code = module["questions"][-1]["question_code"] if module["questions"] else ""
        module_range = (
            f"{_compact_question_code(first_code)}-{_compact_question_code(last_code)}"
            if first_code and last_code
            else "当前题目"
        )
        weak_questions = sorted(module["questions"], key=lambda question: question["score_rate"])[:3]
        core_items = _core_diagnosis_items(module, module_analysis, weak_questions)
        core_rows = "".join(f"<li>{_escape(item)}</li>" for item in core_items)
        evidence_rows = "".join(
            f'<li><strong>{_escape(_compact_question_code(question["question_code"]))} {_escape(question["short_title"])}</strong>（{question["score_out_of_4"]:.2f}/4）：{_escape((interpretation_map.get(question["question_code"]) or {}).get("text") or _default_signal(question))}</li>'
            for question in weak_questions
        )
        brand = (
            f'<img class="brand-logo" src="{logo_uri}" alt="优鲲智能 U-KUN AI" />'
            if logo_uri
            else '<div class="brand-fallback">AI DIAGNOSIS</div>'
        )
        module_heading = (
            f'{_escape(module["module_name"])} '
            f'<span class="module-meta">（{_escape(module_range)}，满分{module["max_score"]}分，'
            f'均分{module_average:.2f}/4，<span style="color:{_score_color(module["score_rate"])}">'
            f'{_escape(module["risk_level"])}）</span></span>'
        )
        module_pages.append(
            f'''<section class="page module-score-page">
  <header class="reference-header"><div class="title-mark"></div><div class="title-wrap"><h2>{module_heading}</h2><p>{_escape(company.get("company_name"))} · {_escape(organization.get("department"))} · {_escape(organization.get("position"))}</p></div><div class="brand-cluster">{brand}<span>组织内部诊断报告 · V{version}</span></div></header>
  <div class="module-score-grid"><div class="chart-panel">{_radar_svg(module)}<div class="module-average">模块均分 <strong>{module_average:.2f}</strong> / 4</div></div>
  <div class="table-panel"><table><thead><tr><th>题项</th><th>均分/4</th><th>风险等级</th><th>信号解读</th></tr></thead><tbody>{rows}</tbody></table></div></div>
  <div class="score-legend"><b>分数说明：</b><span><i class="legend-excellent"></i>3.1-4 优秀</span><span><i class="legend-good"></i>2.1-3 良好</span><span><i class="legend-weak"></i>1.1-2 较弱</span><span><i class="legend-risk"></i>0-1 高风险</span></div>
</section>
<section class="page module-insight-page">
  <header class="reference-header"><div class="title-mark"></div><div class="title-wrap"><h2>{module_heading}</h2><p>{_escape(company.get("company_name"))} · {_escape(organization.get("department"))} · {_escape(organization.get("position"))}</p></div><div class="brand-cluster">{brand}<span>组织内部诊断报告 · V{version}</span></div></header>
  <div class="insight-body"><section class="core-diagnosis"><h3>【核心诊断】</h3><ul>{core_rows}</ul></section>
  <section class="root-cause"><h3>▶ 深层根因：</h3><p>{_escape(root_cause)}</p></section>
  <section class="evidence-note"><h3>答卷信号摘要（待内部核验）</h3><ul>{evidence_rows}</ul><p class="boundary">本页依据：部门负责人本次答卷、固定评分规则及企业已有诊断信息。未使用访谈原声，也未将企业公开信息直接写成部门内部事实。</p></section></div>
</section>'''
        )
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><style>
@page {{ size: 297mm 167mm; margin: 0; }}
* {{ box-sizing: border-box; }} body {{ margin:0; color:#172c49; font-family:"Microsoft YaHei","Noto Sans CJK SC",Arial,sans-serif; background:#dcecff; }}
.page {{ width:297mm; height:167mm; padding:4mm 6.5mm 4mm; page-break-after:always; position:relative; overflow:hidden; background:linear-gradient(120deg,#dfefff 0%,#edf7ff 48%,#d2e5ff 100%); }}
.page::before {{ content:""; position:absolute; inset:0; background-image:linear-gradient(rgba(72,129,198,.10) 1px,transparent 1px),linear-gradient(90deg,rgba(72,129,198,.10) 1px,transparent 1px); background-size:31mm 31mm; pointer-events:none; }}
.page > * {{ position:relative; }} .reference-header {{ align-items:center; display:flex; gap:3.5mm; height:20mm; }} .title-mark {{ background:#5840d8; height:11mm; width:2.1mm; flex:0 0 auto; }} .title-wrap {{ min-width:0; flex:1 1 auto; }} .title-wrap h2 {{ color:#050505; font-size:30px; font-weight:900; letter-spacing:.01em; line-height:1.15; margin:0; white-space:nowrap; }} .module-meta {{ font-size:16px; font-weight:800; }} .title-wrap p {{ color:#52718f; font-size:10.5px; margin:2px 0 0; }}
.brand-cluster {{ align-items:flex-end; display:flex; flex:0 0 43mm; flex-direction:column; gap:1px; justify-content:center; }} .brand-logo {{ height:auto; max-height:13mm; object-fit:contain; width:42mm; }} .brand-cluster span {{ color:#58718d; font-size:7.5px; }} .brand-fallback {{ color:#4634bd; font-size:12px; font-weight:900; }}
.module-score-grid {{ column-gap:3%; display:grid; grid-template-columns:31% 63%; height:132mm; align-items:stretch; }} .chart-panel {{ align-items:center; background:transparent; display:flex; flex-direction:column; justify-content:center; padding:2mm 1mm 0 0; }} .chart-panel svg {{ height:124mm; width:100%; }} .module-average {{ color:#54708b; font-size:11px; margin-top:-1mm; }} .module-average strong {{ color:#1d3150; font-size:15px; }}
.table-panel {{ border:1.2px solid #ad6b36; border-radius:0; height:100%; overflow:hidden; background:rgba(239,248,255,.26); }} table {{ border-collapse:collapse; height:100%; table-layout:fixed; width:100%; font-size:13px; }} th {{ background:#3e2f87; color:#fff; font-size:14px; font-weight:800; padding:8px 10px; text-align:center; }} td {{ border:1px solid #3d4d64; font-size:12.5px; line-height:1.42; padding:7px 9px; vertical-align:middle; word-break:break-word; }} tbody tr:nth-child(even) {{ background:rgba(255,255,255,.26); }} th:nth-child(1) {{ width:24%; }} th:nth-child(2) {{ text-align:center; width:13%; }} th:nth-child(3) {{ text-align:center; width:16%; }} th:nth-child(4) {{ width:47%; }} .score-cell {{ font-size:15px; font-weight:900; text-align:center; }} .risk {{ border-radius:999px; display:inline-block; font-size:11.5px; font-weight:800; padding:3px 7px; white-space:nowrap; }} .signal-text {{ color:#242424; font-size:12px; line-height:1.5; }} .signal-emphasis {{ color:#4e3bc2; font-weight:800; }}
.score-legend {{ align-items:center; bottom:2mm; display:flex; font-size:11px; gap:8mm; justify-content:center; left:34%; position:absolute; right:4%; }} .score-legend b {{ color:#222; font-weight:700; }} .score-legend span {{ align-items:center; display:inline-flex; gap:2mm; white-space:nowrap; }} .score-legend i {{ display:inline-block; height:4mm; width:4mm; }} .legend-excellent {{ background:#22694f; }} .legend-good {{ background:#25ad82; }} .legend-weak {{ background:#b85c08; }} .legend-risk {{ background:#d40000; }}
.module-insight-page {{ padding-bottom:4mm; }} .insight-body {{ display:flex; flex-direction:column; height:137mm; padding:3mm 2mm 0; }} .core-diagnosis {{ flex:0 0 auto; }} .core-diagnosis h3 {{ color:#111; font-size:16px; margin:0 0 2.5mm; }} .core-diagnosis ul, .evidence-note ul {{ list-style:none; margin:0; padding:0; }} .core-diagnosis li {{ color:#101010; font-size:13px; line-height:1.75; padding-left:7mm; position:relative; }} .core-diagnosis li::before {{ color:#3f35b6; content:"✧"; font-size:17px; left:0; position:absolute; top:0; }} .root-cause {{ background:linear-gradient(90deg,#766bd0,#887fda); border:1px solid #5d52b8; color:#fff; margin:8mm 0 7mm; padding:5mm 7mm; }} .root-cause h3 {{ color:#fff; font-size:16px; margin:0 0 2mm; }} .root-cause p {{ color:#fff; font-size:15px; font-weight:800; line-height:1.65; margin:0; }} .evidence-note {{ border:1px dashed #9db3ca; border-radius:9px; color:#54708b; margin-top:auto; padding:4mm 6mm; }} .evidence-note h3 {{ color:#4f6580; font-size:12px; font-style:italic; margin:0 0 2mm; }} .evidence-note li {{ font-size:10px; line-height:1.55; margin:1mm 0; }} .evidence-note li strong {{ color:#253f64; }} .evidence-note .boundary {{ border-top:1px solid rgba(120,151,181,.35); font-size:9px; line-height:1.5; margin:3mm 0 0; padding-top:2mm; }}
.radar-ring {{ fill:none; stroke:#c4d5e6; stroke-width:1; }} .radar-axis {{ stroke:#d2deea; stroke-width:1; }} .radar-baseline {{ fill:none; stroke:#ed8b73; stroke-dasharray:5 4; stroke-width:1.6; }} .radar-value {{ fill:rgba(29,115,92,.20); stroke:#21684f; stroke-width:2.2; }} .radar-point {{ fill:#21684f; stroke:#fff; stroke-width:1.5; }} .radar-label,.legend-text,.radar-scale {{ fill:#2d6b54; font-size:9px; }} .legend-line {{ stroke:#21684f; stroke-width:2; }} .legend-baseline {{ stroke:#ef816c; stroke-width:1.5; stroke-dasharray:4 3; }}
</style></head><body>{"".join(module_pages)}</body></html>'''


def _stored_summary(payload: OrganizationReportPayload) -> dict[str, Any]:
    """Persist scores and IDs, not a questionnaire text snapshot."""

    data = payload.data
    return {
        "report_format_version": data["report_format_version"],
        "enterprise_report_id": payload.enterprise_report_id,
        "score": data["score"],
        "modules": [
            {
                "module_code": module["module_code"],
                "module_name": module["module_name"],
                "raw_score": module["raw_score"],
                "max_score": module["max_score"],
                "score_rate": module["score_rate"],
                "risk_level": module["risk_level"],
                "questions": [
                    {
                        "question_id": question["question_id"],
                        "question_code": question["question_code"],
                        "answer_value": question["answer_value"],
                        "max_score": question["max_score"],
                        "score_rate": question["score_rate"],
                    }
                    for question in module["questions"]
                ],
            }
            for module in data["modules"]
        ],
    }


def _validate_pdf(pdf_bytes: bytes) -> None:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise OrganizationReportError("PDF文件头校验失败")
    try:
        pages = len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception as exc:  # noqa: BLE001
        raise OrganizationReportError("PDF无法读取") from exc
    if pages < 2:
        raise OrganizationReportError("PDF页数不足，报告内容可能不完整")


def prepare_auto_analysis(db: Session, submission_id: int) -> None:
    """After answer commit, decide eligibility and create at most one auto task."""

    submission = organization_report_repo.get_submission(db, submission_id)
    if submission is None or submission.status != OrganizationSubmissionStatus.submitted.value:
        return
    enterprise_report, _research = _load_valid_enterprise_report(db, submission.company_name)
    if enterprise_report is None:
        submission.analysis_status = OrganizationAnalysisStatus.not_eligible.value
        submission.analysis_note = "该企业暂无有效企业诊断报告，暂不执行组织AI分析。"
        db.commit()
        return
    if organization_report_repo.has_submitted_same_department(db, submission):
        submission.analysis_status = OrganizationAnalysisStatus.waiting_manual.value
        submission.analysis_note = "同一企业同一部门已有提交，等待管理员人工决定是否生成。"
        db.commit()
        return
    if organization_report_repo.get_active_task_for_submission(db, submission.id):
        return
    organization_report_repo.create_report_task(
        db,
        submission=submission,
        source_enterprise_report_id=enterprise_report.id,
        task_kind=OrganizationReportTaskKind.automatic.value,
    )
    submission.analysis_status = OrganizationAnalysisStatus.queued.value
    submission.analysis_note = "已进入组织分析队列。"
    db.commit()


def queue_manual_analysis(db: Session, submission_id: int) -> tuple[OrganizationReport, OrganizationReportTask]:
    submission = organization_report_repo.get_submission(db, submission_id)
    if submission is None:
        raise OrganizationReportError("组织答卷不存在")
    if submission.status != OrganizationSubmissionStatus.submitted.value:
        raise OrganizationReportConflictError("只有已提交的组织答卷可以生成报告")
    if organization_report_repo.get_active_task_for_submission(db, submission.id):
        raise OrganizationReportConflictError("该组织答卷已有分析任务正在处理")
    enterprise_report, _research = _load_valid_enterprise_report(db, submission.company_name)
    if enterprise_report is None:
        raise OrganizationReportNotEligibleError("该企业暂无有效的企业诊断报告，暂不可生成组织分析")
    report, task = organization_report_repo.create_report_task(
        db,
        submission=submission,
        source_enterprise_report_id=enterprise_report.id,
        task_kind=OrganizationReportTaskKind.manual.value,
    )
    submission.analysis_status = OrganizationAnalysisStatus.queued.value
    submission.analysis_note = "管理员已发起组织分析。"
    db.commit()
    db.refresh(report)
    return report, task


async def _generate_analysis(db: Session, payload: OrganizationReportPayload) -> tuple[dict[str, Any], str]:
    validation_errors: list[str] = []
    last_error = ""
    for _attempt in range(1, MAX_AI_ATTEMPTS + 1):
        try:
            raw, model_name = await call_organization_llm(db, payload, validation_errors or None)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            validation_errors = [last_error]
            continue
        parsed = _parse_json(raw)
        validation_errors = validate_analysis(parsed, payload)
        if not validation_errors and parsed is not None:
            return parsed, model_name
        last_error = "；".join(validation_errors)
    raise OrganizationReportContentError(last_error or "AI组织分析内容不完整")


async def process_organization_report_task(task_id: int, lock_token: str | None = None) -> bool:
    db = SessionLocal()
    try:
        task = db.get(OrganizationReportTask, task_id)
        if task is None:
            return True
        token = lock_token or task.lock_token
        if task.status != OrganizationReportTaskStatus.processing.value or not token or task.lock_token != token:
            return False
        submission = organization_report_repo.get_submission_with_answers(db, task.organization_submission_id)
        report = organization_report_repo.get_report(db, task.organization_report_id)
        if submission is None or report is None:
            raise OrganizationReportError("组织报告任务关联数据不存在")
        submission.analysis_status = OrganizationAnalysisStatus.processing.value
        report.status = OrganizationReportStatus.generating.value
        report.generation_started_at = utc_now()
        db.commit()
        payload = build_current_payload(db, submission)
        analysis, model_name = await _generate_analysis(db, payload)
        report.html_content = render_organization_report_html(payload, analysis, report.version)
        report.pdf_content = await asyncio.to_thread(render_report_pdf_bytes_with_browser_html, report.html_content.encode("utf-8"))
        _validate_pdf(report.pdf_content)
        report.summary_json = json.dumps(_stored_summary(payload), ensure_ascii=False)
        report.analysis_json = json.dumps(analysis, ensure_ascii=False)
        report.source_enterprise_report_id = payload.enterprise_report_id
        report.model_name = model_name
        report.status = OrganizationReportStatus.generated.value
        report.generation_completed_at = utc_now()
        report.generation_error = None
        task.status = OrganizationReportTaskStatus.succeeded.value
        task.last_error = None
        task.completed_at = utc_now()
        task.locked_at = None
        task.lock_token = None
        submission.analysis_status = OrganizationAnalysisStatus.generated.value
        submission.analysis_note = f"已生成V{report.version}组织分析PDF。"
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("组织诊断报告任务失败：task_id=%s", task_id)
        db.rollback()
        task = db.get(OrganizationReportTask, task_id)
        if task is not None and task.status == OrganizationReportTaskStatus.processing.value:
            report = db.get(OrganizationReport, task.organization_report_id)
            submission = db.get(OrganizationSubmission, task.organization_submission_id)
            message = str(exc)[:2000]
            if report is not None:
                report.status = OrganizationReportStatus.failed.value
                report.generation_error = message
                report.generation_completed_at = utc_now()
            task.status = OrganizationReportTaskStatus.failed.value
            task.last_error = message
            task.completed_at = utc_now()
            task.locked_at = None
            task.lock_token = None
            if submission is not None:
                submission.analysis_status = (
                    OrganizationAnalysisStatus.not_eligible.value
                    if isinstance(exc, OrganizationReportNotEligibleError)
                    else OrganizationAnalysisStatus.failed.value
                )
                submission.analysis_note = message
            db.commit()
        return False
    finally:
        db.close()


async def run_organization_report_worker(poll_interval_seconds: float = 2.0) -> None:
    while True:
        db = SessionLocal()
        try:
            claimed = organization_report_repo.claim_next_task(db, utc_now())
        finally:
            db.close()
        if claimed is None:
            await asyncio.sleep(poll_interval_seconds)
            continue
        task_id, lock_token = claimed
        await process_organization_report_task(task_id, lock_token)

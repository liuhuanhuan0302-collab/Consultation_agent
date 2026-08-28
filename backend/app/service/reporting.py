"""
报告生成服务 — 案例推荐、AI 调用、HTML 渲染。

流程：
  1. 取低分维度 → 匹配案例
  2. 组装结构化 payload
  3. 调用 DeepSeek API 生成报告建议
  4. AI 成功且模板完整 → generated；失败或不完整 → failed，转人工审核
  5. 写入 Report 表 + Recommendation 关联表
"""

import html
import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass

import httpx
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import AiConversationMessage, CaseStudy, CompanyLead, DimensionScore, Report, ReportStatus
from app.repositories.case_repo import get_active_cases_by_modules, get_active_generic_cases
from app.service.api_gateway_service import effective_llm_override
from app.service.company_research import research_section_text
from app.service.report_content import sanitize_report_content
from app.service.report_analysis import build_core_findings, build_question_scores
from app.service.system_setting_service import report_contact_snapshot
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)
_report_generation_semaphore: asyncio.Semaphore | None = None
REPORT_FORMAT_VERSION = 2


def _load_company_research(report: Report) -> dict | None:
    """读取报告的公司情报结果，损坏时静默跳过。"""
    if not report.company_research_json:
        return None
    try:
        research = json.loads(report.company_research_json)
    except json.JSONDecodeError:
        return None
    return research if isinstance(research, dict) else None


def report_generation_semaphore() -> asyncio.Semaphore:
    global _report_generation_semaphore
    if _report_generation_semaphore is None:
        concurrency = max(1, get_settings().report_generation_concurrency)
        _report_generation_semaphore = asyncio.Semaphore(concurrency)
    return _report_generation_semaphore


def is_mysql_retryable_lock_error(exc: OperationalError) -> bool:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    return bool(args and args[0] in {1205, 1213})


def clean_advisor_text(text: str) -> str:
    """删除模型返回里的客套开头、邮件格式和重复标题。"""
    cleaned = text.strip()
    markers = ["本次诊断结果显示", "本次诊断显示", "诊断结果显示"]
    marker_positions = [cleaned.find(marker) for marker in markers if marker in cleaned]
    if marker_positions:
        cleaned = cleaned[min(marker_positions):]
    cleaned = re.sub(r"^好的，.*?\n+", "", cleaned, flags=re.S)
    cleaned = re.sub(r"^---+\s*", "", cleaned)
    cleaned = re.sub(r"^#{1,6}\s*\*\*.*?报告\*\*\s*", "", cleaned)
    cleaned = re.sub(r"^\*\*(致|发件人|主题)[:：]\*\*.*?\n", "", cleaned, flags=re.M)
    cleaned = re.sub(r"^\*\*(致|发件人|主题)[:：].*?\*\*\s*.*?\n", "", cleaned, flags=re.M)
    cleaned = re.sub(r"^尊敬的.*?团队[，,：:]?\s*", "", cleaned)
    return cleaned.strip()


def render_markdown_like_text(text: str) -> str:
    """将模型返回的简易 Markdown 文本转成报告内可读 HTML。"""
    lines = [line.strip() for line in clean_advisor_text(text).replace("\r\n", "\n").split("\n")]
    parts: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        if list_items:
            parts.append("<ul>" + "".join(list_items) + "</ul>")
            list_items.clear()

    def inline_markup(value: str) -> str:
        escaped = html.escape(value)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    for line in lines:
        if not line or line in {"---", "```"}:
            flush_list()
            continue
        if line.startswith("```"):
            flush_list()
            continue
        heading = re.match(r"^#{1,6}\s*(.+)$", line)
        if heading:
            flush_list()
            title = heading.group(1).strip().strip("*").strip()
            if any(word in title for word in ["诊断补充建议报告", "管理摘要"]):
                continue
            parts.append(f"<h4>{inline_markup(title)}</h4>")
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if bullet:
            list_items.append(f"<li>{inline_markup(bullet.group(1))}</li>")
            continue
        parts.append(f"<p>{inline_markup(line)}</p>")

    flush_list()
    return "".join(parts)


def select_recommendations(db: Session, lead: CompanyLead, dimensions: list[DimensionScore], limit: int = 5) -> list[CaseStudy]:
    """
    根据低分维度和行业匹配推荐案例。
    优先匹配同行业案例，数量不足时用通用案例补齐。
    保证返回至少 3 条推荐（如果案例库足够）。
    """
    low_dimensions = sorted(dimensions, key=lambda item: item.score_rate)[:3]
    low_codes = [dimension.module.code for dimension in low_dimensions]
    cases = get_active_cases_by_modules(db, low_codes)

    industry = lead.industry or ""
    industry_matches = [case for case in cases if case.industry in {industry, "通用"}]
    selected = industry_matches[:limit]
    if len(selected) < limit:
        selected.extend([case for case in cases if case not in selected][: limit - len(selected)])
    if len(selected) < 3:
        selected.extend(get_active_generic_cases(db, limit - len(selected)))
    return selected[:limit]


def condense_research(research: dict | None) -> str | None:
    """把 7 维情报压缩为简短事实摘要，供报告提示词引用。"""
    if not research:
        return None
    labels = {
        "company_overview": "公司介绍",
        "revenue_scale": "营收规模",
        "products": "产品",
        "industry_characteristics": "行业特点",
        "development_status": "发展现状",
        "challenges": "可能遇到的挑战",
        "ai_opportunities": "AI 机会",
    }
    parts = [f"{label}：{(research_section_text(research.get(key)) or '未披露')[:240]}" for key, label in labels.items()]
    return "；".join(parts)


def build_report_payload(
    lead: CompanyLead,
    report: Report,
    dimensions: list[DimensionScore],
    cases: list[CaseStudy],
    research: dict | None = None,
    report_contact: dict[str, str] | None = None,
) -> dict:
    """
    组装发送给 LLM 的结构化诊断数据。
    包含企业信息、总分、维度明细、低分维度、推荐案例，以及联网检索到的公司公开信息。
    此数据同时存入 Report.summary_json 供前端图表使用。
    """
    submission = report.submission
    low_dimensions = sorted(dimensions, key=lambda item: item.score_rate)[:3]
    question_scores = build_question_scores(report)
    public_info = condense_research(research)
    return {
        "report_format_version": REPORT_FORMAT_VERSION,
        "report_contact": dict(report_contact or {}),
        "company": {
            "name": lead.company_name,
            "city": lead.city,
            "industry": lead.industry,
            "size": lead.company_size,
            "position": lead.position,
            "ai_focus": lead.ai_focus,
            "public_info": public_info,
        },
        "company_research": research or {},
        "score": {
            "total": submission.total_score,
            "max_score": submission.max_score,
            "score_rate": submission.score_rate,
        },
        "customer_classification": {
            "lead_level": lead.lead_level,
            "demand_summary": lead.demand_summary,
        },
        "dimensions": [
            {
                "module_code": score.module.code,
                "module_name": score.module.name,
                "raw_score": score.raw_score,
                "max_score": score.max_score,
                "score_rate": score.score_rate,
            }
            for score in sorted(dimensions, key=lambda item: item.module.sort_order)
        ],
        "low_dimensions": [
            {
                "module_code": score.module.code,
                "module_name": score.module.name,
                "raw_score": score.raw_score,
                "max_score": score.max_score,
                "score_rate": score.score_rate,
            }
            for score in low_dimensions
        ],
        "question_scores": question_scores,
        "core_findings": build_core_findings(dimensions, question_scores),
        "cases": [
            {
                "title": case.title,
                "industry": case.industry,
                "function_area": case.function_area,
                "priority_tag": case.priority_tag,
                "description": case.description,
                "expected_benefit": case.expected_benefit,
            }
            for case in cases
        ],
    }


def _report_prompt_payload(payload: dict) -> dict:
    """Exclude renderer-only metadata from data sent to the language model."""

    return {
        key: value
        for key, value in payload.items()
        if key not in {"report_format_version", "report_contact"}
    }


def render_report_contact_html(payload: dict) -> str:
    """Render the contact snapshot captured for this report, if populated."""

    contact = payload.get("report_contact") or {}
    labels = (
        ("contact_name", "联系人"),
        ("phone", "电话"),
        ("wechat", "微信号"),
        ("email", "邮箱"),
    )
    details = " | ".join(
        f'{label}：{html.escape(value)}'
        for key, label in labels
        if (value := str(contact.get(key) or "").strip())
    )
    if not details:
        return ""
    return f"""
      <section class="report-contact-section report-diagnosis-callout report-contact-callout">
        <p>如需入企调研或进一步了解，可以联系：</p>
        <p>{details}</p>
      </section>
    """


def render_fallback_html(payload: dict, model_text: str | None = None) -> str:
    """
    渲染 HTML 报告——AI 失败时独立使用，AI 成功时追加 AI 补充建议块。
    FIXME: 当前 HTML 模板内嵌在代码中，后续考虑用 Jinja2 模板分离。
    """
    company = payload["company"]
    score = payload["score"]
    low_dimensions = payload["low_dimensions"]
    core_findings = payload.get("core_findings") or []
    cases = payload["cases"]
    classification = payload.get("customer_classification") or {}
    company_name = html.escape(company.get("name") or "该企业")
    ai_focus = html.escape(company.get("ai_focus") or "暂未补充")
    demand_summary = html.escape(classification.get("demand_summary") or ai_focus)
    weakest_dimension = low_dimensions[0] if low_dimensions else None
    weakest_dimension_name = html.escape(str(weakest_dimension.get("module_name") or "关键能力")) if weakest_dimension else "关键能力"
    weakest_dimension_rate = round(float(weakest_dimension.get("score_rate") or 0) * 100) if weakest_dimension else 0
    short_cards = "".join(
        f"""
        <li><strong>{html.escape(item["module_name"])}</strong> 当前得分率 {round(item["score_rate"] * 100)}%，建议优先拆解业务动作、数据输入和组织责任。</li>
        """
        for item in low_dimensions
    )
    finding_rows = "".join(
        f"""
        <tr>
          <td>{index}</td>
          <td><strong>{html.escape(str(item.get("finding") or ""))}</strong></td>
          <td>{html.escape(str(item.get("evidence") or ""))}<br /><span class="report-table-note">{html.escape(str(item.get("meaning") or ""))}</span></td>
        </tr>
        """
        for index, item in enumerate(core_findings, start=1)
    )
    finding_section = f"""
      <section>
        <h3>核心发现与证据</h3>
        <table class="report-finding-table">
          <thead><tr><th>序号</th><th>核心发现</th><th>证据与含义</th></tr></thead>
          <tbody>{finding_rows}</tbody>
        </table>
      </section>
    """ if finding_rows else ""
    case_cards = "".join(
        f"""
        <section class="report-case">
          <h4>{html.escape(case["title"])}</h4>
          <p>{html.escape(case["description"])}</p>
          <p><strong>预期收益：</strong>{html.escape(case["expected_benefit"])}</p>
        </section>
        """
        for case in cases
    )

    ai_block = ""
    if model_text:
        ai_block = f"""
        <section>
          <h3>AI 顾问补充建议</h3>
          <div class="report-ai-text">{render_markdown_like_text(model_text)}</div>
        </section>
        """

    return sanitize_report_content(f"""
    <article class="report-document">
      <section>
        <h2>一、执行摘要</h2>
        <div class="report-diagnosis-callout">
          <strong>一句话总诊断</strong>
          <p>{company_name}本次诊断得分为 {score["total"]}/{score["max_score"]}，当前应优先关注{weakest_dimension_name}（得分率 {weakest_dimension_rate}%）。报告用于识别 AI 转型的准备度与优先验证方向，不直接等同于经营结果或组织能力的客观审计。</p>
        </div>
        <p><strong>当前诉求：</strong>{demand_summary}</p>
      </section>
      {finding_section}
      <section>
        <h2>二、关键短板与验证方向</h2>
        <ol>{short_cards}</ol>
      </section>
      <section>
        <h2>三、优先 AI 场景建议</h2>
        {case_cards}
      </section>
      {ai_block}
      {render_report_contact_html(payload)}
    </article>
    """)


def build_deepseek_prompt(payload: dict) -> str:
    """构建 DeepSeek API 提示词，要求输出五部分结构化 JSON。"""
    dimensions = payload.get("dimensions") or []
    validation_feedback = payload.get("_report_validation_feedback") or []
    correction_notice = ""
    if validation_feedback:
        correction_notice = (
            "\n上一次输出未通过完整性校验，请修正以下问题后重新输出完整 JSON：\n- "
            + "\n- ".join(str(item) for item in validation_feedback)
            + "\n"
        )
    return f"""
你是一名资深的企业 AI 原生转型咨询顾问。请基于以下结构化诊断数据（答题得分、客户诉求、公司联网公开信息），生成一份高价值诊断报告。
{correction_notice}

报告必须包含 5 个部分，严格按以下 JSON 结构输出（只输出 JSON，不要 markdown 代码块，不要任何解释文字）：

{{
  "executive_summary": [
    {{"finding": "核心发现（一句话）", "evidence": "证据与含义（必须引用具体题目编号与得分、维度得分率）"}}
  ],
  "dimension_analysis": [
    {{
      "module_code": "M01",
      "module_name": "维度简称",
      "core_conclusion": "核心结论（一句话：该维度得分率 + 总体特征定性）",
      "evidence_rows": [
        {{"evidence": "数据依据（引用题号、题干与得分，如 Q4“用户满意度/NPS/复购率在战略目标和绩效考核中的权重”得分4/4（100%））", "interpretation": "分析解读（解释该组数据说明的管理含义）"}}
      ]
    }}
  ],
  "key_contradictions": [
    {{"contradiction": "矛盾名（如：局部清晰 vs. 整体模糊）", "evidence": "证据（引用得分对比）", "diagnosis": "诊断（一句话点破本质）"}}
  ],
  "workshop_topics": [
    {{"priority": "P0", "topic": "议题", "question": "现场核心问题", "deliverable": "必须产出", "nature": "必须形成共识/必须形成选择/必须明确机制"}}
  ],
  "ai_scenarios": [
    {{"name": "场景名", "description": "场景描述", "benefit": "预期收益"}}
  ]
}}

要求：
1. executive_summary 4-6 条，每条必须引用具体题目编号/得分率作为证据，不得空泛套话。
2. dimension_analysis 必须覆盖全部 {len(dimensions)} 个模块，逐个结合该模块对应题目的得分给出分析，按 module_code 与下方诊断数据中的 dimensions 一致。每个模块按“核心结论 / 数据依据 / 分析解读”三栏组织：
   - core_conclusion：一句话核心结论（包含该维度得分率与总体特征定性，如“该维度得分率46.43%，呈现‘理念强、机制弱’的特征。”）。
   - evidence_rows：3-5 行，每行是“数据依据 + 分析解读”配对；数据依据必须引用具体题号、题干与得分（含百分比），按“高分项 → 中分项 → 低分/0分项”的顺序组织；分析解读解释该组数据反映的管理含义。
   - 最后一行 evidence_rows 的 interpretation 应落到“对该公司业务意味着什么 + 具体建议”。
3. key_contradictions 3-5 条，体现“强项与弱项之间的张力”，证据必须来自得分对比（如某维度高 vs 另一维度低）。
4. workshop_topics 4-6 条，用 P0/P1/P2 分级，议题要贴合该公司所处行业与当前现状。
5. ai_scenarios 通常提供 3-5 个，必须结合下方“公司公开信息”中的行业、业务、挑战与 AI 机会，给出贴合该公司实际的具体场景；可靠证据不足时可减少数量，不得为了凑数套用无关行业案例。不要生成“适用方向”字段，不要使用“攻坚战”“闪电战”“升维战”等战法判断。
6. 不得生成管理层行动建议、实施时间表或其他第六章节。
7. 不得编造客户未填写的答题数据；不得改写评分数字和得分率。
8. 语气专业、务实，面向 CEO 和高管可读。

诊断数据：
{json.dumps(_report_prompt_payload(payload), ensure_ascii=False, indent=2)}
""".strip()


def parse_structured_report(text: str) -> dict | None:
    """解析 AI 返回的结构化报告 JSON，容忍 markdown 代码块包裹与前后杂质。"""
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


REPORT_SECTION_KEYS = [
    "executive_summary",
    "dimension_analysis",
    "key_contradictions",
    "workshop_topics",
    "ai_scenarios",
]


class ReportContentInvalidError(RuntimeError):
    """AI 报告三次生成后仍不符合固定模板，必须转人工审核。"""

    def __init__(self, detail: str, *, payload: dict | None = None, messages: list[dict] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.payload = payload or {}
        self.messages = messages or []


@dataclass(frozen=True)
class ReportGenerationCandidate:
    """A fully validated report snapshot that has not yet mutated persistence."""

    payload: dict
    html_content: str
    cases: tuple[CaseStudy, ...]
    messages: tuple[dict, ...]
    model_name: str


def report_data_validation_errors(data: dict | None, payload: dict) -> list[str]:
    """校验五个模板部分均有内容，且逐维分析覆盖全部有效模块。"""
    if not data:
        return ["未返回可解析的 JSON 报告"]
    errors: list[str] = []
    labels = {
        "executive_summary": "执行摘要",
        "dimension_analysis": "能力成熟度逐维分析",
        "key_contradictions": "关键矛盾与核心诊断",
        "workshop_topics": "工作坊议题地图",
        "ai_scenarios": "优先 AI 应用场景",
    }
    for key in REPORT_SECTION_KEYS:
        value = data.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"缺少或未填写：{labels[key]}")

    expected_codes = {
        str(item.get("module_code") or "").strip().upper()
        for item in (payload.get("dimensions") or [])
        if str(item.get("module_code") or "").strip()
    }
    actual_codes = {
        str(item.get("module_code") or "").strip().upper()
        for item in (data.get("dimension_analysis") or [])
        if isinstance(item, dict) and str(item.get("module_code") or "").strip()
    }
    missing_codes = sorted(expected_codes - actual_codes)
    if missing_codes:
        errors.append(f"逐维分析未覆盖模块：{', '.join(missing_codes)}")
    return errors


def _report_data_usable(data: dict | None, payload: dict | None = None) -> bool:
    """兼容旧调用；新流程必须通过完整模板校验。"""
    if payload is None:
        if not data:
            return False
        keys = REPORT_SECTION_KEYS
        return all(bool(data.get(key)) for key in keys)
    return not report_data_validation_errors(data, payload)


def render_structured_report_html(payload: dict, data: dict) -> str:
    """
    渲染 AI 生成的结构化诊断报告。
      一、执行摘要（表格） / 二、能力成熟度逐维分析 / 三、关键矛盾与核心诊断（表格）
      v2：四、工作坊议题地图（表格） / 五、优先 AI 场景建议（结合公司情报）/ 进一步沟通
      旧快照缺少版本号时继续保留历史第五、六章节格式。
    雷达图与能力成熟度排行由前端基于 summary_json 渲染，不重复输出。
    """
    company = payload.get("company") or {}
    dimensions = payload.get("dimensions") or []
    company_name = html.escape(company.get("name") or "该企业")
    is_v2 = int(payload.get("report_format_version") or 1) >= REPORT_FORMAT_VERSION

    # 一、执行摘要
    summary_items = data.get("executive_summary") or []
    summary_rows = "".join(
        f"""
        <tr>
          <td>{index}</td>
          <td><strong>{html.escape(str(item.get("finding") or ""))}</strong></td>
          <td>{html.escape(str(item.get("evidence") or ""))}</td>
        </tr>
        """
        for index, item in enumerate(summary_items, start=1)
    )

    # 二、能力成熟度逐维分析：每个模块一个三栏表格（核心结论 | 数据依据 | 分析解读）
    analysis_by_code = {
        str(item.get("module_code") or "").upper(): item
        for item in (data.get("dimension_analysis") or [])
    }
    module_tables = ""
    for dim in dimensions:
        code = str(dim.get("module_code") or "").upper()
        name = html.escape(str(dim.get("module_name") or ""))
        rate = round(float(dim.get("score_rate") or 0) * 100)
        raw = dim.get("raw_score")
        max_score = dim.get("max_score")
        analysis_item = analysis_by_code.get(code) or {}
        core_conclusion = str(analysis_item.get("core_conclusion") or "").strip()
        evidence_rows = analysis_item.get("evidence_rows") or []
        if rate < 25:
            rate_class = "rate-danger"
        elif rate < 50:
            rate_class = "rate-warn"
        elif rate < 75:
            rate_class = "rate-ok"
        else:
            rate_class = "rate-good"
        score_note = f"（{raw}/{max_score}）" if raw is not None and max_score else ""
        module_head = (
            f'<div class="report-module-head">{code} {name} · 得分率 '
            f'<span class="report-dimension-rate {rate_class}">{rate}%</span>{score_note}</div>'
        )
        if core_conclusion and evidence_rows:
            rows_html = ""
            for index, row in enumerate(evidence_rows):
                evidence = str(row.get("evidence") or "").strip()
                interpretation = str(row.get("interpretation") or "").strip()
                conclusion_cell = (
                    f'<td class="report-cad-conclusion">{html.escape(core_conclusion)}</td>'
                    if index == 0
                    else '<td class="report-cad-conclusion"></td>'
                )
                rows_html += f"""
                <tr>
                  {conclusion_cell}
                  <td class="report-cad-evidence">{html.escape(evidence)}</td>
                  <td class="report-cad-interpretation">{html.escape(interpretation)}</td>
                </tr>
                """
            module_tables += f"""
            <div class="report-module-block">
              {module_head}
              <table class="report-finding-table report-cad-table">
                <thead><tr><th>核心结论</th><th>数据依据</th><th>分析解读</th></tr></thead>
                <tbody>{rows_html}</tbody>
              </table>
            </div>
            """
        else:
            # 兼容旧格式：仅有一段分析文本
            analysis = str(analysis_item.get("analysis") or "").strip()
            if not analysis:
                analysis = f"{dim.get('module_name')}维度得分率为 {rate}%，建议结合具体业务场景进一步核验短板与负责人。"
            module_tables += f"""
            <div class="report-module-block">
              {module_head}
              <div class="report-module-body">{html.escape(analysis)}</div>
            </div>
            """

    # 三、关键矛盾与核心诊断
    contradiction_rows = "".join(
        f"""
        <tr>
          <td><strong>{html.escape(str(item.get("contradiction") or ""))}</strong></td>
          <td>{html.escape(str(item.get("evidence") or ""))}</td>
          <td>{html.escape(str(item.get("diagnosis") or ""))}</td>
        </tr>
        """
        for item in (data.get("key_contradictions") or [])
    )

    # 四、工作坊议题地图
    workshop_rows = "".join(
        f"""
        <tr>
          <td><span class="report-priority">{html.escape(str(item.get("priority") or ""))}</span></td>
          <td><strong>{html.escape(str(item.get("topic") or ""))}</strong></td>
          <td>{html.escape(str(item.get("question") or ""))}</td>
          <td>{html.escape(str(item.get("deliverable") or ""))}</td>
          <td>{html.escape(str(item.get("nature") or ""))}</td>
        </tr>
        """
        for item in (data.get("workshop_topics") or [])
    )

    # 五、优先 AI 场景
    scenario_cards = "".join(
        f"""
        <section class="report-case">
          <h4>{index}. {html.escape(str(item.get("name") or ""))}</h4>
          <p>{html.escape(str(item.get("description") or ""))}</p>
          <p><strong>预期收益：</strong>{html.escape(str(item.get("benefit") or ""))}</p>
        </section>
        """
        for index, item in enumerate((data.get("ai_scenarios") or []), start=1)
    )

    if is_v2:
        section_five_title = "五、优先 AI 场景建议"
        section_five_note = "以下场景仅供决策参考，具体需入企调研后给出更详细的建议。"
        closing_section = render_report_contact_html(payload)
    else:
        section_five_title = "五、优先 AI 场景与案例"
        section_five_note = f"以下场景基于本次诊断结果与 {company_name} 的公开信息生成，仅供决策参考。"
        action_items = "".join(
            f"<li>{html.escape(str(action))}</li>"
            for action in (data.get("management_actions") or [])
        )
        closing_section = f"""
      <section>
        <h2>六、管理层行动建议</h2>
        <ol class="report-action-list">{action_items}</ol>
      </section>
        """

    return sanitize_report_content(f"""
    <article class="report-document">
      <section>
        <h2>一、执行摘要</h2>
        <table class="report-finding-table">
          <thead><tr><th>序号</th><th>核心发现</th><th>证据与含义</th></tr></thead>
          <tbody>{summary_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>二、能力成熟度分析</h2>
        <p class="report-section-note">以下按模块逐项分析（含该模块题目得分明细），与上方雷达图、得分排行一一对应。</p>
        <div class="report-module-tables">{module_tables}</div>
      </section>
      <section>
        <h2>三、关键矛盾与核心诊断</h2>
        <table class="report-finding-table report-contradiction-table">
          <thead><tr><th>关键矛盾</th><th>证据</th><th>诊断</th></tr></thead>
          <tbody>{contradiction_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>四、工作坊议题地图</h2>
        <table class="report-finding-table report-workshop-table">
          <thead><tr><th>优先级</th><th>议题</th><th>现场核心问题</th><th>必须产出</th><th>性质</th></tr></thead>
          <tbody>{workshop_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>{section_five_title}</h2>
        <p class="report-section-note report-section-note--accent">{section_five_note}</p>
        {scenario_cards}
      </section>
      {closing_section}
    </article>
    """)


async def call_deepseek(payload: dict, llm_override: "LlmGatewayOverride | None" = None) -> str | None:
    """
    异步调用 LLM 生成报告正文（Chat Completions）。
    优先使用网关配置的 LLM（后台「API 配置」页），未配置时回退 .env 的 deepseek_*。
    温度 0.35 保证输出稳定可控。无可用 Key 时返回 None，触发 fallback 渲染。
    """
    settings = get_settings()
    override_key = llm_override.api_key if llm_override else None
    override_base = (llm_override.base_url or "").strip() if llm_override else ""
    base_url = override_base or settings.deepseek_base_url
    model = (llm_override.model if llm_override else None) or settings.deepseek_model
    # 安全约束：网关保存了自定义 LLM 地址、但网关 Key 不可用（如加密密钥
    # 轮换后无法解密）时，禁止把 .env 的 DeepSeek Key 发往该地址。
    if override_base and not override_key:
        raise RuntimeError(
            "LLM 接口地址已配置但网关 Key 无法解密（加密密钥可能已轮换），请在后台重新填写 LLM API Key 并保存"
        )
    api_key = override_key or settings.deepseek_api_key
    if not api_key:
        return None
    # 报告提示词大、要求结构化输出，生成耗时较长，用更宽松的超时避免读取响应体超时
    timeout = max(settings.deepseek_timeout_seconds, 120)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是严谨的企业转型咨询报告生成助手。"},
                    {"role": "user", "content": build_deepseek_prompt(payload)},
                ],
                "temperature": 0.35,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def store_ai_message(
    db: Session,
    report: Report,
    role: str,
    content: str,
    purpose: str = "report_advisor",
    metadata: dict | None = None,
) -> None:
    """保存模型相关上下文，便于后续重新进入、后台复盘和顾问继续跟进。"""
    db.add(
        AiConversationMessage(
            lead_id=report.submission.lead_id,
            submission_id=report.submission_id,
            report_id=report.id,
            purpose=purpose,
            role=role,
            content=content,
            model_vendor="deepseek",
            model_name=get_settings().deepseek_model,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
    )


async def generate_report_candidate(db: Session, report: Report) -> ReportGenerationCandidate:
    """Generate and validate a V2 candidate without changing the stored report."""

    lead = report.submission.lead
    dimensions = list(report.submission.dimension_scores)
    cases = select_recommendations(db, lead, dimensions)
    research = _load_company_research(report)
    payload = build_report_payload(
        lead,
        report,
        dimensions,
        cases,
        research=research,
        report_contact=report_contact_snapshot(db),
    )
    model_text = None
    report_data: dict | None = None
    validation_errors: list[str] = []
    generation_errors: list[str] = []
    messages: list[dict] = []
    llm_override = effective_llm_override(db)
    for attempt in range(1, 4):
        attempt_payload = dict(payload)
        if validation_errors:
            attempt_payload["_report_validation_feedback"] = validation_errors
        prompt = build_deepseek_prompt(attempt_payload)
        messages.append({
            "role": "user",
            "content": prompt,
            "metadata": {"payload": payload, "attempt": attempt, "validation_feedback": validation_errors},
        })
        try:
            model_text = await call_deepseek(attempt_payload, llm_override=llm_override)
        except Exception as exc:  # noqa: BLE001
            generation_errors.append(f"第 {attempt} 次调用失败：{exc}")
            validation_errors = [generation_errors[-1]]
            continue
        if not model_text:
            generation_errors.append(f"第 {attempt} 次调用未返回内容")
            validation_errors = [generation_errors[-1]]
            continue
        messages.append({"role": "assistant", "content": model_text, "metadata": {"attempt": attempt}})
        candidate = parse_structured_report(model_text)
        validation_errors = report_data_validation_errors(candidate, payload)
        if not validation_errors:
            report_data = candidate
            break
        generation_errors.append(f"第 {attempt} 次结构不完整：{'；'.join(validation_errors)}")

    if report_data is None:
        detail = "报告内容不完整，待人工审核：" + "；".join(generation_errors[-3:])
        raise ReportContentInvalidError(detail, payload=payload, messages=messages)

    return ReportGenerationCandidate(
        payload=payload,
        html_content=render_structured_report_html(payload, report_data),
        cases=tuple(cases),
        messages=tuple(messages),
        model_name=get_settings().deepseek_model,
    )


def apply_report_candidate(db: Session, report: Report, candidate: ReportGenerationCandidate) -> None:
    """Atomically-ready persistence mutations for an already validated candidate."""

    db.query(AiConversationMessage).filter(
        AiConversationMessage.report_id == report.id,
        AiConversationMessage.purpose == "report_advisor",
    ).delete()
    for message in candidate.messages:
        store_ai_message(
            db,
            report,
            message["role"],
            message["content"],
            metadata=message.get("metadata"),
        )

    report.status = ReportStatus.generated.value
    report.generation_completed_at = utc_now()
    report.generation_error = None
    report.summary_json = json.dumps(candidate.payload, ensure_ascii=False)
    report.model_name = candidate.model_name
    report.html_content = candidate.html_content
    report.recommendations.clear()
    db.flush()

    from app.models import Recommendation

    for index, case in enumerate(candidate.cases):
        db.add(
            Recommendation(
                report_id=report.id,
                case_id=case.id,
                reason=f"匹配低分维度与行业方向，建议优先级第 {index + 1}。",
                priority_score=100 - index * 10,
            )
        )


async def generate_report_content(db: Session, report: Report) -> Report:
    """
    报告生成编排——核心链路。
    ① 取低分维度 + 行业匹配案例
    ② 调用 DeepSeek，并对固定模板完整性最多校验重试 3 次
    ③ 渲染 HTML 写入 report
    ④ 创建案例推荐关联记录
    """
    report.generation_started_at = utc_now()
    report.generation_completed_at = None
    try:
        candidate = await generate_report_candidate(db, report)
    except ReportContentInvalidError as exc:
        db.query(AiConversationMessage).filter(
            AiConversationMessage.report_id == report.id,
            AiConversationMessage.purpose == "report_advisor",
        ).delete()
        for message in exc.messages:
            store_ai_message(
                db,
                report,
                message["role"],
                message["content"],
                metadata=message.get("metadata"),
            )
        report.summary_json = json.dumps(exc.payload, ensure_ascii=False)
        report.model_name = get_settings().deepseek_model
        report.status = ReportStatus.failed.value
        report.generation_completed_at = utc_now()
        report.html_content = ""
        report.generation_error = exc.detail
        db.flush()
        return report

    apply_report_candidate(db, report, candidate)
    return report


async def regenerate_report_content_for_testing(db: Session, report: Report) -> Report:
    """仅供本地开发环境重跑当前报告，不触发邮件或投递队列。"""
    await generate_report_content(db, report)
    db.commit()
    db.refresh(report)
    return report


async def try_generate_report_content_now(db: Session, report: Report) -> bool:
    """
    当前进程还有空闲生成名额时，直接为前台请求生成报告。
    忙碌时返回 False，由提交接口继续走后台队列，避免用户长时间等待。
    """
    semaphore = report_generation_semaphore()
    if getattr(semaphore, "_value", 0) <= 0:
        return False
    await semaphore.acquire()
    try:
        report.status = ReportStatus.generating.value
        db.flush()
        await generate_report_content(db, report)
        return True
    finally:
        semaphore.release()


async def generate_report_content_for_id(report_id: int) -> None:
    """
    后台生成报告。
    提交接口只负责入队并快速返回；这里用信号量限制 DeepSeek 并发，避免 100 个用户同时把模型接口打满。
    """
    async with report_generation_semaphore():
        for attempt in range(3):
            db = SessionLocal()
            try:
                report = db.query(Report).filter(Report.id == report_id).first()
                if not report:
                    return
                if report.status in {ReportStatus.generated.value, ReportStatus.fallback.value} and report.html_content:
                    return
                report.status = ReportStatus.generating.value
                db.commit()
                db.refresh(report)
                await generate_report_content(db, report)
                db.commit()
                return
            except OperationalError as exc:
                db.rollback()
                if not is_mysql_retryable_lock_error(exc) or attempt == 2:
                    logger.exception("后台报告生成失败: report_id=%s", report_id)
                    return
                await asyncio.sleep(0.2 * (attempt + 1))
            except Exception:
                logger.exception("后台报告生成失败: report_id=%s", report_id)
                db.rollback()
                return
            finally:
                db.close()

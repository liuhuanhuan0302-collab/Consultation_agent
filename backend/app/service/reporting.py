"""
报告生成服务 — 案例推荐、AI 调用、HTML 渲染。

流程：
  1. 取低分维度 → 匹配案例
  2. 组装结构化 payload
  3. 调用 DeepSeek API 生成报告建议
  4. AI 成功 → generated 状态；失败 → fallback 状态，用模板渲染 HTML
  5. 写入 Report 表 + Recommendation 关联表
"""

import html
import asyncio
import json
import logging
import re
from dataclasses import asdict

import httpx
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import AiConversationMessage, CaseStudy, CompanyLead, DimensionScore, Report, ReportStatus
from app.repositories.case_repo import get_active_cases_by_modules, get_active_generic_cases
from app.service.company_research import render_company_research_html

logger = logging.getLogger(__name__)
_report_generation_semaphore: asyncio.Semaphore | None = None


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
    parts = [f"{label}：{str(research.get(key) or '未披露').strip()[:120]}" for key, label in labels.items()]
    return "；".join(parts)


def build_report_payload(lead: CompanyLead, report: Report, dimensions: list[DimensionScore], cases: list[CaseStudy], research: dict | None = None) -> dict:
    """
    组装发送给 LLM 的结构化诊断数据。
    包含企业信息、总分、维度明细、低分维度、推荐案例，以及联网检索到的公司公开信息。
    此数据同时存入 Report.summary_json 供前端图表使用。
    """
    submission = report.submission
    low_dimensions = sorted(dimensions, key=lambda item: item.score_rate)[:3]
    public_info = condense_research(research)
    return {
        "company": {
            "name": lead.company_name,
            "industry": lead.industry,
            "size": lead.company_size,
            "position": lead.position,
            "ai_focus": lead.ai_focus,
            "public_info": public_info,
        },
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


def render_fallback_html(payload: dict, model_text: str | None = None) -> str:
    """
    渲染 HTML 报告——AI 失败时独立使用，AI 成功时追加 AI 补充建议块。
    FIXME: 当前 HTML 模板内嵌在代码中，后续考虑用 Jinja2 模板分离。
    """
    company = payload["company"]
    score = payload["score"]
    dimensions = payload["dimensions"]
    low_dimensions = payload["low_dimensions"]
    cases = payload["cases"]
    classification = payload.get("customer_classification") or {}
    company_name = html.escape(company.get("name") or "该企业")
    industry = html.escape(company.get("industry") or "未填写行业")
    ai_focus = html.escape(company.get("ai_focus") or "暂未补充")
    lead_level = html.escape(classification.get("lead_level") or "未判定")
    demand_summary = html.escape(classification.get("demand_summary") or ai_focus)

    dimension_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(item["module_name"])}</td>
          <td>{item["raw_score"]}/{item["max_score"]}</td>
          <td>{round(item["score_rate"] * 100)}%</td>
        </tr>
        """
        for item in dimensions
    )
    short_cards = "".join(
        f"""
        <li><strong>{html.escape(item["module_name"])}</strong> 当前得分率 {round(item["score_rate"] * 100)}%，建议优先拆解业务动作、数据输入和组织责任。</li>
        """
        for item in low_dimensions
    )
    case_cards = "".join(
        f"""
        <section class="report-case">
          <h4>{html.escape(case["title"])}</h4>
          <p><strong>适用方向：</strong>{html.escape(case["function_area"])} · {html.escape(case["priority_tag"])}</p>
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

    return f"""
    <article class="report-document">
      <section>
        <h2>管理摘要</h2>
        <p>{company_name} 当前总分为 {score["total"]}/{score["max_score"]}。本报告基于企业填写的诊断量表生成，适合用于识别短板、筛选优先 AI 场景，并作为后续顾问访谈的前置材料。</p>
        <p><strong>客户等级：</strong>{lead_level}</p>
        <p><strong>当前诉求：</strong>{demand_summary}</p>
      </section>
      <section>
        <h2>10 维得分</h2>
        <table>
          <thead><tr><th>维度</th><th>得分</th><th>得分率</th></tr></thead>
          <tbody>{dimension_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>核心短板</h2>
        <ol>{short_cards}</ol>
      </section>
      <section>
        <h2>优先 AI 场景与案例</h2>
        {case_cards}
      </section>
      {ai_block}
      <section>
        <h2>下一步建议</h2>
        <p>建议安排一次 60-90 分钟顾问诊断会，围绕低分维度确认业务目标、数据基础、流程责任和速赢项目，优先选择高 ROI、低协作阻力的场景进入试点。</p>
      </section>
    </article>
    """


def build_deepseek_prompt(payload: dict) -> str:
    """构建 DeepSeek API 提示词，注入结构化诊断数据 + 角色设定 + 输出要求。"""
    return f"""
你是一名企业 AI 原生转型咨询顾问。请基于以下结构化诊断数据输出中文报告补充建议。
要求：
1. 不要编造客户未填写的事实。
2. 不要改写评分数字和得分率。
3. 第一节必须使用标题“AI 当前问题分析”，篇幅约 700-1000 个中文字符。结合企业填写的诉求、行业和各维度得分，围绕 2-3 个核心问题分别说明：问题表现、答题或维度得分依据、对业务效率/客户体验/经营决策的影响、以及建议优先处理的动作。不得只罗列低分项，也不要使用空泛套话。
4. 后续输出包括管理摘要、三条关键短板解释、三到五个优先 AI 场景、下一步咨询建议。
5. 语气专业、务实，面向 CEO 和高管可读。
6. 不要输出邮件格式、致/发件人/主题、代码块、分隔线，也不要重复报告标题和总分卡片。
7. 结合 customer_classification 中的客户等级和当前诉求提出建议；不要使用“风险等级”或“建议打法”等分类标签。
8. 使用清晰小标题和自然段即可。

诊断数据：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


async def call_deepseek(payload: dict) -> str | None:
    """
    异步调用 DeepSeek Chat API。
    温度 0.35 保证输出稳定可控。
    API Key 未配置时返回 None，触发 fallback 渲染。

    FIXME: DeepSeek 返回格式偶有不稳定（如 JSON 被 markdown 包裹），
           当前直接用原始文本，后续考虑增加结构化解析。
    FIXME: 网络超时/服务不可用时 raise_for_status 会抛异常，
           上游 generate_report_content 会捕获并降级，但未做重试。
    """
    settings = get_settings()
    if not settings.deepseek_api_key:
        return None
    async with httpx.AsyncClient(timeout=settings.deepseek_timeout_seconds, trust_env=False) as client:
        response = await client.post(
            f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.deepseek_model,
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


async def generate_report_content(db: Session, report: Report) -> Report:
    """
    报告生成编排——核心链路。
    ① 取低分维度 + 行业匹配案例
    ② 调用 DeepSeek（失败则降级到模板）
    ③ 渲染 HTML 写入 report
    ④ 创建案例推荐关联记录
    """
    lead = report.submission.lead
    dimensions = list(report.submission.dimension_scores)
    cases = select_recommendations(db, lead, dimensions)
    research = _load_company_research(report)
    payload = build_report_payload(lead, report, dimensions, cases, research=research)
    model_text = None
    status = ReportStatus.fallback.value
    error = None
    db.query(AiConversationMessage).filter(AiConversationMessage.report_id == report.id).delete()
    prompt = build_deepseek_prompt(payload)
    store_ai_message(db, report, "user", prompt, metadata={"payload": payload})
    try:
        model_text = await call_deepseek(payload)
        if model_text:
            status = ReportStatus.generated.value
            store_ai_message(db, report, "assistant", model_text)
    except Exception as exc:
        # 报告生成失败不阻塞客户提交流程，降级到模板报告
        error = str(exc)

    report.status = status
    report.summary_json = json.dumps(payload, ensure_ascii=False)
    report.model_name = get_settings().deepseek_model
    report.generation_error = error
    html = render_fallback_html(payload, model_text=model_text)
    if research:
        html += render_company_research_html(research)
    report.html_content = html
    report.recommendations.clear()
    db.flush()

    from app.models import Recommendation

    for index, case in enumerate(cases):
        db.add(
            Recommendation(
                report_id=report.id,
                case_id=case.id,
                reason=f"匹配低分维度与行业方向，建议优先级第 {index + 1}。",
                priority_score=100 - index * 10,
            )
        )
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

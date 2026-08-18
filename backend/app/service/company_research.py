"""客户公司联网情报 — 搜索 + DeepSeek 提炼 7 维信息与 AI 转型分析。

流程：
  1. search_company_web() 按网关配置调用搜索 API，多查询收集公开信息
  2. build_research_prompt() 组装 7 维 + 分析提示词
  3. 调用 DeepSeek，parse_research_response() 解析 JSON
  4. 结果写入 report.company_research_json 并留痕

失败一律返回 None，绝不影响报告生成主流程。
"""

import json
import logging
import re
from html import escape

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AiConversationMessage, Report
from app.service.api_gateway_service import (
    DEFAULT_DEEPSEEK_SEARCH_MODEL,
    LlmGatewayOverride,
    SearchGatewayConfig,
    effective_llm_override,
    effective_search_config,
)
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

SECTION_LABELS: list[tuple[str, str]] = [
    ("company_overview", "公司介绍"),
    ("revenue_scale", "营收规模"),
    ("products", "产品"),
    ("industry_characteristics", "行业特点"),
    ("development_status", "发展现状"),
    ("challenges", "可能遇到的挑战"),
    ("ai_opportunities", "AI 能帮他们做什么"),
]

RESEARCH_QUERIES = [
    "{company} 公司简介 主营业务 成立时间",
    "{company} 营收 融资 员工规模",
    "{company} 产品 解决方案 客户",
    "{company} 最新动态 新闻 里程碑",
    "{company} 所处行业 市场格局 竞争",
    "{company} 经营挑战 风险 瓶颈",
]

SEARCH_TEXT_LIMIT = 20000


def format_search_results(results: list[dict], limit: int = SEARCH_TEXT_LIMIT) -> str:
    """把搜索结果拼成编号文本，控制总长避免提示词爆炸。"""
    lines: list[str] = []
    total = 0
    for index, item in enumerate(results, 1):
        line = f"[{index}] {item.get('title') or ''}\n    {item.get('snippet') or ''}\n    {item.get('url') or ''}"
        if total + len(line) > limit:
            break
        lines.append(line)
        total += len(line)
    return "\n\n".join(lines)


async def _search_once(client: httpx.AsyncClient, config: SearchGatewayConfig, query: str, count: int) -> list[dict]:
    if config.provider == "bocha":
        response = await client.post(
            f"{config.base_url.rstrip('/')}/web-search",
            headers={"Authorization": f"Bearer {config.api_key}"},
            json={"query": query, "count": count, "summary": False},
        )
        response.raise_for_status()
        pages = response.json().get("data", {}).get("webPages", {}).get("value", [])
        return [
            {"title": page.get("name") or page.get("snippetTitle") or "", "snippet": page.get("snippet") or page.get("summary") or "", "url": page.get("url") or ""}
            for page in pages
            if isinstance(page, dict)
        ][:count]
    if config.provider == "serpapi":
        response = await client.get(
            f"{config.base_url.rstrip('/')}/search",
            params={"engine": "google", "q": query, "api_key": config.api_key, "num": count, "hl": "zh-cn"},
        )
        response.raise_for_status()
        return [
            {"title": item.get("title", ""), "snippet": item.get("snippet", ""), "url": item.get("link", "")}
            for item in response.json().get("organic_results", [])
            if isinstance(item, dict)
        ][:count]
    # custom：通用 GET，q/api_key/count 参数，兼容常见搜索接口的返回结构
    response = await client.get(
        config.base_url.rstrip("/"),
        params={"q": query, "api_key": config.api_key, "count": count},
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("results") or payload.get("data") or payload.get("organic_results") or []
    if isinstance(items, dict):
        items = items.get("items") or items.get("results") or []
    return [
        {"title": item.get("title", ""), "snippet": item.get("snippet") or item.get("content") or "", "url": item.get("url") or item.get("link") or ""}
        for item in items
        if isinstance(item, dict)
    ][:count]


async def search_single_query(config: SearchGatewayConfig, query: str) -> list[dict]:
    """单查询检索 — 供配置连通性测试使用。不跟随重定向，防止地址被劫持到内网。"""
    async with httpx.AsyncClient(timeout=config.timeout_seconds, trust_env=False, follow_redirects=False) as client:
        return await _search_once(client, config, query, count=config.max_results)


async def search_company_web(config: SearchGatewayConfig, company_name: str) -> list[dict]:
    """按配置对目标公司做多查询检索，单查询与汇总均严格不超过 max_results。"""
    queries = [query.format(company=company_name) for query in RESEARCH_QUERIES]
    collected: list[dict] = []
    async with httpx.AsyncClient(timeout=config.timeout_seconds, trust_env=False, follow_redirects=False) as client:
        for query in queries:
            try:
                collected.extend(await _search_once(client, config, query, count=config.max_results))
            except Exception as exc:
                logger.warning("公司情报检索失败 query=%s: %s", query, exc)
    unique: list[dict] = []
    seen: set[str] = set()
    for item in collected:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= config.max_results:
            break
    return unique


def build_research_prompt(company: dict, search_text: str, dimensions: list[dict]) -> str:
    """组装 7 维情报 + 综合分析的提示词（配合外部搜索 API 结果使用）。"""
    low_dimensions = sorted(dimensions, key=lambda item: item["score_rate"])[:3]
    return f"""你是企业情报与 AI 转型分析助手。请基于以下公开网络检索结果，对目标公司输出结构化情报。

要求：
1. 严格基于检索结果，不得编造事实；营收、融资、人数等数字必须来自检索结果，检索不到时写"公开渠道未披露"。
2. 每个情报字段 200-400 字，语言精炼、信息密度高，面向转型顾问使用；尽量覆盖时间、数字、主体等可核实细节。
3. "analysis" 字段 500-800 字：结合公司情报、客户自述信息与诊断答题得分，给出该公司 AI 转型的综合分析——先结合得分率最低的维度诊断现状，再给出 2-3 条最值得做的 AI 场景建议，并说明与客户诉求的关系。
4. "sources" 列出实际引用的来源，每项含 title 与 url。
5. 只输出 JSON，不要 markdown 代码块，不要任何解释文字。

输出字段说明：
- company_overview：公司介绍（成立时间、主营业务、行业地位等）
- revenue_scale：营收规模（营收、融资、人员规模等公开数据，无则写"公开渠道未披露"）
- products：产品（主要产品线与解决方案）
- industry_characteristics：行业特点（所处行业的市场格局与发展趋势）
- development_status：发展现状（近期动态、里程碑、荣誉等）
- challenges：可能遇到的挑战（经营与转型中面临的风险）
- ai_opportunities：AI 能帮他们做什么（基于情报判断的 AI 应用机会）

输出格式：
{{
  "company_overview": "...",
  "revenue_scale": "...",
  "products": "...",
  "industry_characteristics": "...",
  "development_status": "...",
  "challenges": "...",
  "ai_opportunities": "...",
  "analysis": "...",
  "sources": [{{"title": "...", "url": "..."}}]
}}

客户自述信息：
{json.dumps(company, ensure_ascii=False, indent=2)}

诊断答题结果（各维度得分率）：
{json.dumps(dimensions, ensure_ascii=False, indent=2)}

得分率最低的三个维度：
{json.dumps(low_dimensions, ensure_ascii=False, indent=2)}

公开网络检索结果：
{search_text}
""".strip()


def build_deepseek_research_prompt(company: dict, dimensions: list[dict]) -> str:
    """组装一步式提示词（配合 DeepSeek 原生联网搜索使用，无需外部搜索结果）。"""
    low_dimensions = sorted(dimensions, key=lambda item: item["score_rate"])[:3]
    return f"""你是企业情报与 AI 转型分析助手。请使用联网搜索工具（web_search）检索目标公司的公开信息，然后输出结构化情报。

要求：
1. 先联网检索公司介绍、营收融资规模、产品、行业格局、近期动态、经营挑战等信息，必要时多轮搜索补充；数字必须来自搜索结果，检索不到时写"公开渠道未披露"，不得编造。
2. 每个情报字段 200-400 字，语言精炼、信息密度高，面向转型顾问使用；尽量覆盖时间、数字、主体等可核实细节。
3. "analysis" 字段 500-800 字：结合检索到的公司情报、客户自述信息与诊断答题得分，给出该公司 AI 转型的综合分析——先结合得分率最低的维度诊断现状，再给出 2-3 条最值得做的 AI 场景建议，并说明与客户诉求的关系。
4. "sources" 列出实际引用的来源，每项含 title 与 url（必须来自搜索引用）。
5. 只输出 JSON，不要 markdown 代码块，不要任何解释文字。

输出字段说明：
- company_overview：公司介绍（成立时间、主营业务、行业地位等）
- revenue_scale：营收规模（营收、融资、人员规模等公开数据，无则写"公开渠道未披露"）
- products：产品（主要产品线与解决方案）
- industry_characteristics：行业特点（所处行业的市场格局与发展趋势）
- development_status：发展现状（近期动态、里程碑、荣誉等）
- challenges：可能遇到的挑战（经营与转型中面临的风险）
- ai_opportunities：AI 能帮他们做什么（基于情报判断的 AI 应用机会）

输出格式：
{{
  "company_overview": "...",
  "revenue_scale": "...",
  "products": "...",
  "industry_characteristics": "...",
  "development_status": "...",
  "challenges": "...",
  "ai_opportunities": "...",
  "analysis": "...",
  "sources": [{{"title": "...", "url": "..."}}]
}}

目标公司：
{json.dumps(company, ensure_ascii=False, indent=2)}

诊断答题结果（各维度得分率）：
{json.dumps(dimensions, ensure_ascii=False, indent=2)}

得分率最低的三个维度：
{json.dumps(low_dimensions, ensure_ascii=False, indent=2)}
""".strip()


def parse_research_response(text: str) -> dict | None:
    """解析模型输出：容忍 markdown 代码块包裹与前后杂质。"""
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


async def _chat_completion(system: str, user: str, override: LlmGatewayOverride) -> str | None:
    """调用 LLM：网关覆盖优先，回退 .env 的 deepseek_* 配置。

    安全约束：网关保存了自定义 LLM 地址、但网关 Key 不可用（如加密密钥
    轮换后无法解密）时，禁止把 .env 的 DeepSeek Key 发往该地址，直接跳过。
    """
    settings = get_settings()
    api_key = override.api_key or settings.deepseek_api_key
    if not api_key:
        return None
    base_url = (override.base_url or settings.deepseek_base_url).rstrip("/")
    if override.base_url and not override.api_key:
        logger.warning("网关 LLM 地址已配置但网关 Key 不可用，跳过调用，请管理员重新录入 Key")
        return None
    model = override.model or settings.deepseek_model
    async with httpx.AsyncClient(timeout=settings.deepseek_timeout_seconds, trust_env=False, follow_redirects=False) as client:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.35,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def ping_llm(api_key: str, base_url: str, model: str, timeout_seconds: int) -> str:
    """大模型连通性探测 — 发送一条最小请求，返回模型回复文本。"""
    async with httpx.AsyncClient(timeout=timeout_seconds, trust_env=False, follow_redirects=False) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "请只回复两个字：正常"}],
                "temperature": 0,
                "max_tokens": 16,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def parse_deepseek_responses(data: dict) -> tuple[str, list[dict]]:
    """解析 DeepSeek Responses API 返回：提取正文与引用，统一为 title/snippet/url。

    兼容多种返回结构（output_text 字段 / output 消息列表 / sources / citations /
    web_search_call 的 response.results），最后兜底从正文正则提取 URL。
    """
    text_parts: list[str] = []

    if isinstance(data.get("output_text"), str):
        text_parts.append(data["output_text"])
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") in ("output_text", "text"):
                text_parts.append(str(content.get("text") or ""))
        for result in (item.get("response") or {}).get("results") or []:
            if isinstance(result, dict):
                text_parts.append(str(result.get("summary") or result.get("content") or ""))

    sources: list[dict] = []
    for entry in data.get("sources") or []:
        if isinstance(entry, dict):
            sources.append({"title": entry.get("title") or entry.get("name") or "", "snippet": entry.get("content") or entry.get("snippet") or entry.get("summary") or "", "url": entry.get("url") or ""})
    for citation in data.get("citations") or []:
        if isinstance(citation, dict):
            sources.append({"title": citation.get("title") or "", "snippet": citation.get("content") or citation.get("snippet") or "", "url": citation.get("url") or ""})
    for annotation in data.get("annotations") or []:
        if isinstance(annotation, dict) and isinstance(annotation.get("url_citation"), dict):
            citation = annotation["url_citation"]
            sources.append({"title": citation.get("title") or "", "snippet": citation.get("content") or citation.get("snippet") or "", "url": citation.get("url") or ""})
    for item in data.get("output") or []:
        if isinstance(item, dict) and isinstance(item.get("response"), dict):
            for result in item["response"].get("results") or []:
                if isinstance(result, dict):
                    sources.append({"title": result.get("title") or "", "snippet": result.get("summary") or result.get("content") or "", "url": result.get("url") or ""})

    text = "\n".join(part for part in text_parts if part).strip()
    if not sources:
        for url in re.findall(r"https?://[^\s)\"'<>]+", text):
            sources.append({"title": url, "snippet": "", "url": url})
    unique_sources: list[dict] = []
    seen: set[str] = set()
    for source in sources:
        url = source.get("url") or source.get("title")
        if not url or url in seen:
            continue
        seen.add(url)
        unique_sources.append(source)
    return text, unique_sources


async def call_deepseek_web_search(config: SearchGatewayConfig, prompt: str) -> tuple[str | None, list[dict]]:
    """DeepSeek 原生联网搜索（Responses API + web_search 工具）。返回正文与引用。"""
    model = config.model or DEFAULT_DEEPSEEK_SEARCH_MODEL
    # 联网搜索 + 生成通常较慢（响应体大），用更宽松的超时避免读取响应体时 ReadTimeout
    timeout = max(config.timeout_seconds, 90)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/responses",
            headers={"Authorization": f"Bearer {config.api_key}"},
            json={
                "model": model,
                "input": prompt,
                "tools": [{"type": "web_search"}],
            },
        )
        response.raise_for_status()
        text, sources = parse_deepseek_responses(response.json())
        return (text or None), sources


async def ping_deepseek_search(config: SearchGatewayConfig, query: str) -> tuple[str | None, list[dict]]:
    """DeepSeek 联网搜索连通性探测 — 一条最小检索请求。"""
    return await call_deepseek_web_search(config, f"请联网搜索：{query}，用一句话概括主要信息。")


async def research_company(db: Session, report: Report) -> dict | None:
    """检索目标公司公开信息并生成 7 维情报 + 分析。幂等：已有结果直接返回。"""
    if report.company_research_json:
        try:
            return json.loads(report.company_research_json)
        except json.JSONDecodeError:
            pass

    lead = report.submission.lead
    company_name = (lead.company_name or "").strip()
    if len(company_name) < 4:
        return None
    config = effective_search_config(db)
    if not config:
        return None

    try:
        dimensions = [
            {"module_name": item.module.name, "raw_score": item.raw_score, "max_score": item.max_score, "score_rate": round(item.score_rate, 4)}
            for item in sorted(report.submission.dimension_scores, key=lambda score: score.module.sort_order)
        ]
        company = {
            "name": lead.company_name,
            "industry": lead.industry,
            "size": lead.company_size,
            "annual_revenue": lead.annual_revenue,
            "position": lead.position,
            "ai_focus": lead.ai_focus,
        }
        if config.provider == "deepseek":
            # 一步式：DeepSeek 原生联网搜索直接输出 7 维情报 + 分析 JSON
            prompt = build_deepseek_research_prompt(company, dimensions)
            raw, sources = await call_deepseek_web_search(config, prompt)
            if not raw:
                logger.info("DeepSeek 联网检索无结果 company=%s", company_name)
                return None
            research = parse_research_response(raw)
            if not research:
                logger.warning("公司情报模型输出解析失败 report_id=%s", report.id)
                return None
            results = sources
        else:
            results = await search_company_web(config, company_name)
            if not results:
                logger.info("公司情报检索无结果 company=%s", company_name)
                return None
            search_text = format_search_results(results)
            prompt = build_research_prompt(company, search_text, dimensions)
            raw = await _chat_completion(
                "你是严谨的企业情报与 AI 转型分析助手，输出必须为合法 JSON。",
                prompt,
                effective_llm_override(db),
            )
            if not raw:
                return None
            research = parse_research_response(raw)
            if not research:
                logger.warning("公司情报模型输出解析失败 report_id=%s", report.id)
                return None
    except Exception as exc:
        logger.warning("公司情报检索失败 report_id=%s: %s", report.id, exc)
        return None

    research.setdefault("company_name", company_name)
    research.setdefault("sources", results[:8])
    research["researched_at"] = utc_now().isoformat()
    report.company_research_json = json.dumps(research, ensure_ascii=False)
    metadata = {
        "provider": config.provider,
        "result_count": len(results),
    }
    if config.provider == "deepseek":
        metadata["model"] = config.model or DEFAULT_DEEPSEEK_SEARCH_MODEL
    else:
        metadata["queries"] = [q.format(company=company_name) for q in RESEARCH_QUERIES]
    db.add(
        AiConversationMessage(
            lead_id=lead.id,
            submission_id=report.submission_id,
            report_id=report.id,
            purpose="company_research",
            role="user",
            content=prompt,
            model_vendor="deepseek",
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
    )
    db.add(
        AiConversationMessage(
            lead_id=lead.id,
            submission_id=report.submission_id,
            report_id=report.id,
            purpose="company_research",
            role="assistant",
            content=raw,
            model_vendor="deepseek",
            metadata_json=json.dumps({}, ensure_ascii=False),
        )
    )
    db.flush()
    return research


def render_company_research_html(research: dict) -> str:
    """渲染"企业画像与转型分析"章节，追加到报告 html_content。标签仅用前端白名单内的。"""
    blocks: list[str] = []
    for key, label in SECTION_LABELS:
        text = str(research.get(key) or "").strip()
        if not text:
            continue
        blocks.append(f"<h3>{escape(label)}</h3><p>{escape(text).replace(chr(10), '<br>')}</p>")
    analysis = str(research.get("analysis") or "").strip()
    analysis_html = f"<h3>AI 综合分析</h3><p>{escape(analysis).replace(chr(10), '<br>')}</p>" if analysis else ""
    sources = research.get("sources") or []
    source_items = "".join(
        f'<li><a href="{escape(str(source.get("url") or ""))}" target="_blank" rel="noopener noreferrer">{escape(str(source.get("title") or source.get("url") or ""))}</a></li>'
        for source in sources
        if isinstance(source, dict) and source.get("url")
    )
    source_html = f"<h3>信息来源</h3><ul>{source_items}</ul>" if source_items else ""
    if not blocks and not analysis_html:
        return ""
    return f"""
<section class="company-research">
  <h2>企业画像与转型分析</h2>
  <p class="company-research-note">以下内容由 AI 基于公开网络信息检索生成，仅供决策参考。</p>
  {''.join(blocks)}
  {analysis_html}
  {source_html}
</section>
"""

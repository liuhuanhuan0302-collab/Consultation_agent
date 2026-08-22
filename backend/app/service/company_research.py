"""客户公司联网情报 — 搜索 + DeepSeek 提炼 7 维信息与 AI 转型分析。

流程：
  1. DeepSeek 服务商走官方 Anthropic 协议（/anthropic/v1/messages + 服务端
     web_search），机器引用仅来自 web_search_tool_result 块；
     其他服务商走 search_company_web() 多查询收集公开信息
  2. build_research_prompt() / build_deepseek_research_prompt() 组装情报与来源索引
  3. parse_research_response() 解析 JSON；解析或结构校验失败时复用已有搜索
     结果修正一次（不重新搜索）；API/网络异常不内部重试，交给报告队列退避重试
  4. 结果写入 report.company_research_json 并留痕

失败返回 None 并标记待人工处理，禁止使用空情报生成客户报告。
"""

import json
import logging
import re
from html import escape
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AiConversationMessage, CompanyResearchStatus, Report
from app.service.api_gateway_service import (
    DEFAULT_DEEPSEEK_SEARCH_MODEL,
    LlmGatewayOverride,
    SearchGatewayConfig,
    deepseek_anthropic_messages_url,
    effective_llm_override,
    effective_search_config,
)
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

# pause_turn 协议续传上限：属于同一次调用的协议行为，不算失败重试。
MAX_PAUSE_CONTINUATIONS = 2

# 同一队列任务内 JSON/结构校验失败只修正一次：复用已获得的搜索结果重新生成，
# 不重新搜索，避免与报告队列的退避重试叠加放大 API 调用次数。
RESEARCH_CORRECTION_LIMIT = 1

SECTION_LABELS: list[tuple[str, str]] = [
    ("company_overview", "公司介绍"),
    ("revenue_scale", "营收规模"),
    ("products", "产品与服务"),
    ("industry_characteristics", "行业特点"),
    ("development_status", "发展现状"),
    ("challenges", "可能遇到的挑战"),
    ("ai_opportunities", "AI 能提供的帮助"),
]
ANALYSIS_KEY = "analysis"
MISSING_RESEARCH = "暂未检索到可靠公开信息"
STRUCTURED_SECTION_KEYS = tuple(key for key, _ in SECTION_LABELS) + (ANALYSIS_KEY,)
FACTUAL_SECTION_KEYS = (
    "company_overview",
    "revenue_scale",
    "products",
    "industry_characteristics",
    "development_status",
)


def research_subsections(value: object) -> list[dict[str, str]]:
    """返回清洗后的动态小节；历史字符串数据会由兼容分支单独处理。"""
    if not isinstance(value, list):
        return []
    subsections: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if title and content:
            subsections.append({"title": title, "content": content})
    return subsections


def research_section_text(value: object) -> str:
    """将结构化小节压平为文本，同时兼容历史字符串记录。"""
    if isinstance(value, str):
        return value.strip()
    return "\n".join(f"{item['title']}：{item['content']}" for item in research_subsections(value))


def normalize_source_url(value: object) -> str | None:
    """规范化可核验的 HTTP(S) 来源 URL；拒绝凭据、相对地址和危险协议。

    以 scheme://host[:port]/path 作为来源的唯一身份，剥离查询串与锚点：
    搜索链接常带跟踪参数（?vt=/&utm_ 等），保留会要求模型逐字符复现才能
    通过来源匹配，反而制造误拒。
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    hostname = parsed.hostname.lower().rstrip(".")
    if not hostname:
        return None
    host = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, "", ""))


def trusted_research_sources(citations: list[dict]) -> list[dict[str, str]]:
    """从搜索提供商的真实引用中生成去重后的可信来源清单。"""
    trusted: list[dict[str, str]] = []
    seen: set[str] = set()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        url = normalize_source_url(citation.get("url"))
        if not url or url in seen:
            continue
        title = str(citation.get("title") or "").strip() or url
        trusted.append({"title": title, "url": url})
        seen.add(url)
        if len(trusted) == 8:
            break
    return trusted


def reconcile_research_sources(research: dict, citations: list[dict]) -> list[str]:
    """把模型来源映射到本次搜索引用，并同步重排 source_refs。

    模型主动返回的任意 URL 都不能直接成为证据；只有能按规范化 URL
    精确匹配本次搜索提供商引用的条目才会被保留。
    """
    trusted = trusted_research_sources(citations)
    if not trusted:
        return ["本次搜索没有可核验的 HTTP(S) 引用"]

    model_sources = research.get("sources")
    if not isinstance(model_sources, list) or not model_sources:
        return ["sources 缺失或为空，无法确定 source_refs 与真实引用的对应关系"]

    trusted_by_url = {source["url"]: source for source in trusted}
    canonical: list[dict[str, str]] = []
    canonical_index_by_url: dict[str, int] = {}
    old_to_new: dict[int, int] = {}
    errors: list[str] = []
    for old_index, source in enumerate(model_sources, 1):
        if not isinstance(source, dict):
            errors.append(f"sources 第 {old_index} 条不是来源对象")
            continue
        url = normalize_source_url(source.get("url"))
        if not url or url not in trusted_by_url:
            errors.append(f"sources 第 {old_index} 条未出现在本次搜索引用中")
            continue
        if url not in canonical_index_by_url:
            canonical.append(trusted_by_url[url])
            canonical_index_by_url[url] = len(canonical)
        old_to_new[old_index] = canonical_index_by_url[url]

    if errors:
        return errors

    refs = research.get("source_refs")
    if isinstance(refs, dict):
        remapped: dict[str, object] = {}
        for key, value in refs.items():
            if not isinstance(value, list):
                remapped[key] = value
                continue
            mapped: list[object] = []
            for index in value:
                new_index = old_to_new.get(index) if isinstance(index, int) and not isinstance(index, bool) else None
                candidate: object = new_index if new_index is not None else index
                mapped.append(candidate)
            remapped[key] = mapped
        research["source_refs"] = remapped
    research["sources"] = canonical
    return []


def research_source_indices(research: dict, key: str) -> list[int]:
    """返回某栏目的有效、去重来源序号，供 HTML 与文档统一展示。"""
    sources = research.get("sources")
    refs = research.get("source_refs")
    if not isinstance(sources, list) or not isinstance(refs, dict):
        return []
    values = refs.get(key)
    if not isinstance(values, list):
        return []
    indices: list[int] = []
    for value in values:
        source = sources[value - 1] if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= len(sources) else None
        if (
            isinstance(source, dict)
            and normalize_source_url(source.get("url")) is not None
            and value not in indices
        ):
            indices.append(value)
    return indices


def validate_structured_research(research: dict) -> list[str]:
    """校验本次新生成的数据；读取历史数据时不调用此校验。"""
    errors: list[str] = []
    for key in STRUCTURED_SECTION_KEYS:
        value = research.get(key)
        if value == MISSING_RESEARCH:
            continue
        if not isinstance(value, list) or not 2 <= len(value) <= 5:
            errors.append(f"{key} 必须包含 2-5 个动态小标题，或明确标记未检索到可靠信息")
            continue
        subsections = research_subsections(value)
        if len(subsections) != len(value):
            errors.append(f"{key} 的每个小节都必须同时包含 title 和 content")
            continue
        titles = [item["title"] for item in subsections]
        if len(set(titles)) != len(titles):
            errors.append(f"{key} 的小标题不得重复")
        if any(title.startswith("<") or title in {"其他情况", "补充信息", "动态小标题"} for title in titles):
            errors.append(f"{key} 的小标题必须根据目标公司实际情况生成")

    sources = research.get("sources")
    if not isinstance(sources, list):
        errors.append("sources 必须是引用来源列表")
    elif not sources:
        errors.append("sources 不得为空，报告必须带证据来源")
    else:
        for index, source in enumerate(sources, 1):
            if (
                not isinstance(source, dict)
                or not str(source.get("title") or "").strip()
                or normalize_source_url(source.get("url")) is None
            ):
                errors.append(f"sources 第 {index} 条必须同时包含 title 与 url")
                break

    refs = research.get("source_refs")
    if not isinstance(refs, dict):
        errors.append("source_refs 必须存在，并按顶层字段列出来源序号")
        return errors

    unknown_keys = set(refs) - set(STRUCTURED_SECTION_KEYS)
    if unknown_keys:
        errors.append(f"source_refs 包含未知字段：{', '.join(sorted(unknown_keys))}")

    source_count = len(sources) if isinstance(sources, list) else 0
    for key, value in refs.items():
        if not isinstance(value, list):
            errors.append(f"source_refs.{key} 必须是来源序号列表")
            continue
        seen_indices: set[int] = set()
        for index in value:
            if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= source_count:
                errors.append(f"source_refs.{key} 引用了不存在的来源序号 {index}")
                break
            if index in seen_indices:
                errors.append(f"source_refs.{key} 不得包含重复序号")
                break
            seen_indices.add(index)

    for key in FACTUAL_SECTION_KEYS:
        value = research.get(key)
        indices = refs.get(key)
        if value == MISSING_RESEARCH:
            if indices:
                errors.append(f"source_refs.{key} 在栏目标记无可靠信息时必须为空")
        elif not isinstance(indices, list) or not indices:
            errors.append(f"source_refs.{key} 必须至少引用一个真实来源")
    return errors


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
    """组装 8 栏情报与来源索引的提示词（配合外部搜索 API 结果使用）。"""
    low_dimensions = sorted(dimensions, key=lambda item: item["score_rate"])[:3]
    return f"""你是企业情报与 AI 转型分析助手。请基于以下公开网络检索结果，对目标公司输出结构化情报。

要求：
1. 严格基于检索结果，不得编造事实；营收、融资、人数等数字必须来自检索结果。
2. 8 个顶层字段必须全部存在。每个字段根据该公司的实际信息动态生成 2-5 个小标题，值为对象数组，每项只含 title 和 content；小标题必须具体、互不重复，不得使用“其他情况”“补充信息”等空泛标题。
3. 每个小标题正文建议 80-180 字，语言精炼、信息密度高；如果某个顶层字段确实没有可靠信息，该字段直接写字符串"暂未检索到可靠公开信息"，不得为了凑够小标题而编造或重复。
4. "analysis" 同样输出 2-5 个动态小标题，合计约 500-800 字：结合公司情报、客户自述与诊断得分，诊断现状、优先 AI 场景及其与客户诉求的关系。
5. "sources" 列出实际引用的来源，每项含 title 与 url；"source_refs" 按顶层字段列出引用的来源序号。
6. challenges、ai_opportunities、analysis 是分析判断，不得伪装为已核实事实。
7. 只输出 JSON，不要 markdown 代码块，不要任何解释文字。

输出字段说明：
- company_overview：公司介绍（成立时间、主营业务、行业地位等）
- revenue_scale：营收规模（营收、融资、人员规模等公开数据，无则写"暂未检索到可靠公开信息"）
- products：产品与服务（主要产品线与解决方案）
- industry_characteristics：行业特点（所处行业的市场格局与发展趋势）
- development_status：发展现状（近期动态、里程碑、荣誉等）
- challenges：可能遇到的挑战（经营与转型中面临的风险）
- ai_opportunities：AI 能提供的帮助（基于情报判断的 AI 应用机会）

输出格式：
{{
  "company_overview": [{{"title": "<根据该公司公开信息生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "revenue_scale": [{{"title": "<根据该公司规模信息生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "products": [{{"title": "<根据该公司产品信息生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "industry_characteristics": [{{"title": "<根据该公司所在行业生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "development_status": [{{"title": "<根据该公司发展动态生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "challenges": [{{"title": "<根据该公司具体挑战生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "ai_opportunities": [{{"title": "<根据该公司 AI 机会生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "analysis": [{{"title": "<根据该公司诊断生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "sources": [{{"title": "...", "url": "..."}}],
  "source_refs": {{
    "company_overview": [1],
    "revenue_scale": [1, 2],
    "products": [2],
    "industry_characteristics": [3],
    "development_status": [1, 4]
  }}
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
    """组装一步式 8 栏情报提示词（配合 DeepSeek 原生联网搜索使用）。"""
    low_dimensions = sorted(dimensions, key=lambda item: item["score_rate"])[:3]
    return f"""你是企业情报与 AI 转型分析助手。请使用联网搜索工具（web_search）检索目标公司的公开信息，然后输出结构化情报。

要求：
1. 先联网检索公司介绍、营收融资规模、产品、行业格局、近期动态、经营挑战等信息，必要时多轮搜索补充；数字必须来自搜索结果，不得编造。
2. 8 个顶层字段必须全部存在。每个字段根据该公司的实际信息动态生成 2-5 个小标题，值为对象数组，每项只含 title 和 content；小标题必须具体、互不重复，不得使用“其他情况”“补充信息”等空泛标题。
3. 每个小标题正文建议 80-180 字；如果某个顶层字段确实没有可靠信息，该字段直接写字符串"暂未检索到可靠公开信息"，不得为了凑数量而编造或重复。
4. "analysis" 同样输出 2-5 个动态小标题，合计约 500-800 字：结合公司情报、客户自述与诊断得分，诊断现状、优先 AI 场景及其与客户诉求的关系。
5. "sources" 列出实际引用的来源，每项含 title 与 url（必须来自搜索引用，url 须与搜索结果中的链接精确一致）；"source_refs" 按顶层字段列出引用的来源序号。
6. challenges、ai_opportunities、analysis 是分析判断，不得伪装为已核实事实。
7. 只输出 JSON，不要 markdown 代码块，不要任何解释文字。
8. 严格 JSON 语法：字符串值内如需引用，一律使用中文引号「」或『』，禁止在字符串内使用英文双引号 "；确保输出可被标准 JSON 解析器直接解析。

输出字段说明：
- company_overview：公司介绍（成立时间、主营业务、行业地位等）
- revenue_scale：营收规模（营收、融资、人员规模等公开数据，无则写"暂未检索到可靠公开信息"）
- products：产品与服务（主要产品线与解决方案）
- industry_characteristics：行业特点（所处行业的市场格局与发展趋势）
- development_status：发展现状（近期动态、里程碑、荣誉等）
- challenges：可能遇到的挑战（经营与转型中面临的风险）
- ai_opportunities：AI 能提供的帮助（基于情报判断的 AI 应用机会）

输出格式：
{{
  "company_overview": [{{"title": "<根据该公司公开信息生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "revenue_scale": [{{"title": "<根据该公司规模信息生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "products": [{{"title": "<根据该公司产品信息生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "industry_characteristics": [{{"title": "<根据该公司所在行业生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "development_status": [{{"title": "<根据该公司发展动态生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "challenges": [{{"title": "<根据该公司具体挑战生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "ai_opportunities": [{{"title": "<根据该公司 AI 机会生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "analysis": [{{"title": "<根据该公司诊断生成的小标题1>", "content": "..."}}, {{"title": "<动态小标题2>", "content": "..."}}],
  "sources": [{{"title": "...", "url": "..."}}],
  "source_refs": {{
    "company_overview": [1],
    "revenue_scale": [1, 2],
    "products": [2],
    "industry_characteristics": [3],
    "development_status": [1, 4]
  }}
}}

目标公司：
{json.dumps(company, ensure_ascii=False, indent=2)}

诊断答题结果（各维度得分率）：
{json.dumps(dimensions, ensure_ascii=False, indent=2)}

得分率最低的三个维度：
{json.dumps(low_dimensions, ensure_ascii=False, indent=2)}
""".strip()


def parse_research_response(text: str) -> dict | None:
    """解析模型输出：容忍 markdown 代码块包裹与前后杂质。

    模型偶发在 JSON 字符串值内直接使用英文双引号导致标准 json.loads
    失败；该情况由 research_company 的重试机制兜底（失败自动重试）。
    这里仅做常规的宽松解析。
    """
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    return _loads_lenient(cleaned)


def _loads_lenient(text: str) -> dict | None:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


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


# DeepSeek 服务端联网搜索工具（Anthropic 协议）。
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}

ANTHROPIC_SEARCH_SYSTEM = "你是严谨的企业情报与 AI 转型分析助手，输出必须为合法 JSON。"


def parse_anthropic_response_blocks(data: dict) -> tuple[list[str], list[dict], list[dict]]:
    """解析 Anthropic Messages 响应：返回（正文段落, 机器搜索引用, 原始内容块）。

    只有 web_search_tool_result 块内的 web_search_result 条目算机器引用；
    正文中的 URL、thinking / server_tool_use 块一律不算，防止模型自报网址冒充证据。
    """
    text_parts: list[str] = []
    sources: list[dict] = []
    blocks = [item for item in (data.get("content") or []) if isinstance(item, dict)]
    for block in blocks:
        if block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
        elif block.get("type") == "web_search_tool_result":
            for item in block.get("content") or []:
                if not isinstance(item, dict) or item.get("type") != "web_search_result":
                    continue
                url = str(item.get("url") or "").strip()
                title = str(item.get("title") or "").strip()
                if url or title:
                    sources.append({"title": title or url, "url": url})
    return text_parts, sources, blocks


def build_research_fix_prompt(errors: list[str], trusted_sources: list[dict[str, str]]) -> str:
    """JSON/结构校验失败时的一次性修正提示：复用已有机器搜索结果，禁止再次搜索。"""
    url_list = "\n".join(f"- {source['url']}" for source in trusted_sources) or "（本次没有可用的机器引用）"
    return (
        "你上一条回复未通过校验：\n"
        + "\n".join(f"- {error}" for error in errors)
        + "\n\n请基于对话中已有的 web_search_tool_result 搜索结果重新输出严格 JSON：\n"
        "1. sources 的 url 必须逐条取自以下机器引用（标题可自行概括，URL 必须精确一致）：\n"
        + url_list
        + "\n2. 每个事实栏目的 source_refs 必须指向上述引用中真实使用的序号；"
        "暂未检索到可靠公开信息的栏目写字符串\"暂未检索到可靠公开信息\"且不得写引用。\n"
        "3. 只输出 JSON，不要 markdown 代码块，不要任何解释文字；字符串内禁止使用英文双引号。"
    )


async def call_deepseek_anthropic_search(
    config: SearchGatewayConfig,
    prompt: str,
    *,
    conversation: list[dict] | None = None,
    follow_up_user: str | None = None,
    with_search_tool: bool = True,
) -> tuple[str | None, list[dict], list[dict]]:
    """DeepSeek 官方 Anthropic 协议联网搜索（/anthropic/v1/messages + 服务端 web_search）。

    - 首次调用带 web_search 工具；修正轮传入 conversation（含机器搜索结果）并
      关闭工具，模型只基于已有结果重新输出，不再搜索。
    - stop_reason=pause_turn 时按协议续传：把 assistant 内容原样追加后再次调用，
      最多 MAX_PAUSE_CONTINUATIONS 次；续传属于同一次调用的协议行为，不算失败重试。
    - 返回（正文文本, 机器引用列表, 对话消息列表）；API/网络错误直接抛出，
      由调用方交给报告队列退避重试。
    """
    url = deepseek_anthropic_messages_url(config.base_url)
    messages = [{"role": "user", "content": prompt}]
    if conversation is not None:
        messages = list(conversation)
    if follow_up_user:
        messages.append({"role": "user", "content": follow_up_user})
    timeout = max(config.timeout_seconds, 90)
    text_parts: list[str] = []
    sources: list[dict] = []
    async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
        for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
            body: dict = {
                "model": config.model or DEFAULT_DEEPSEEK_SEARCH_MODEL,
                "max_tokens": 12000,
                "system": ANTHROPIC_SEARCH_SYSTEM,
                "messages": messages,
            }
            if with_search_tool:
                body["tools"] = [WEB_SEARCH_TOOL]
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            parts, block_sources, blocks = parse_anthropic_response_blocks(data)
            text_parts.extend(parts)
            sources.extend(block_sources)
            if data.get("stop_reason") != "pause_turn":
                break
            messages.append({"role": "assistant", "content": blocks})
        else:
            raise RuntimeError(
                f"联网搜索连续 {MAX_PAUSE_CONTINUATIONS + 1} 次 pause_turn 仍未完成，放弃本次调用"
            )
    text = "\n".join(part for part in text_parts if part).strip()
    return (text or None), sources, messages


async def ping_deepseek_search(config: SearchGatewayConfig, query: str) -> tuple[str | None, list[dict]]:
    """DeepSeek 联网搜索连通性探测 — 一条最小检索请求（Anthropic 协议）。"""
    text, sources, _ = await call_deepseek_anthropic_search(config, f"请联网搜索：{query}，用一句话概括主要信息。")
    return text, sources


def _structure_errors(research: dict | None, citations: list[dict]) -> list[str]:
    """解析失败与结构错误统一为错误列表（reconcile 会原位重排 sources/source_refs）。"""
    if research is None:
        return ["模型输出 JSON 解析失败"]
    errors = reconcile_research_sources(research, citations)
    errors.extend(validate_structured_research(research))
    return errors


async def _correct_deepseek_research(
    config: SearchGatewayConfig,
    prompt: str,
    conversation: list[dict],
    machine_sources: list[dict],
    errors: list[str],
) -> tuple[dict | None, list[str]]:
    """修正一次：复用对话中的机器搜索结果（不带搜索工具，不再搜索）。"""
    follow_up = build_research_fix_prompt(errors, trusted_research_sources(machine_sources))
    corrected_raw, _, _ = await call_deepseek_anthropic_search(
        config, prompt, conversation=conversation, follow_up_user=follow_up, with_search_tool=False
    )
    if not corrected_raw:
        return None, ["联网检索无返回结果"]
    research = parse_research_response(corrected_raw)
    final_errors = _structure_errors(research, machine_sources)
    if final_errors:
        return None, final_errors
    return research, []


async def _correct_external_research(
    prompt: str,
    search_results: list[dict],
    errors: list[str],
    llm_override: LlmGatewayOverride,
) -> tuple[dict | None, list[str]]:
    """修正一次：复用已搜索到的公开信息（不重新搜索）。"""
    follow_up = build_research_fix_prompt(errors, trusted_research_sources(search_results))
    corrected_raw = await _chat_completion(
        "你是严谨的企业情报与 AI 转型分析助手，输出必须为合法 JSON。",
        f"{prompt}\n\n{follow_up}",
        llm_override,
    )
    if not corrected_raw:
        return None, ["情报模型无返回"]
    research = parse_research_response(corrected_raw)
    final_errors = _structure_errors(research, search_results)
    if final_errors:
        return None, final_errors
    return research, []


async def research_company(db: Session, report: Report, *, force: bool = False) -> dict | None:
    """检索目标公司公开信息并生成 7 维情报 + 分析。幂等：已有结果直接返回。

    API/网络异常不内部重试，交给报告队列按退避重试；JSON/结构校验失败
    复用已有搜索结果修正一次（不重新搜索），仍失败则把原因写入
    report.generation_error，供后台排查与提醒。
    """
    if report.company_research_json and not force:
        try:
            cached = json.loads(report.company_research_json)
            if cached.get("evidence_version") == 1 and not validate_structured_research(cached):
                report.research_status = CompanyResearchStatus.generated.value
                report.research_completed_at = report.research_completed_at or utc_now()
                return cached
            logger.info("旧版或证据校验失败的企业情报缓存不再复用 report_id=%s", report.id)
        except json.JSONDecodeError:
            pass

    report.research_status = CompanyResearchStatus.processing.value
    report.research_started_at = utc_now()
    report.research_completed_at = None
    report.generation_error = None

    lead = report.submission.lead
    company_name = (lead.company_name or "").strip()
    if not company_name:
        logger.warning("公司情报检索跳过：公司名称为空 report_id=%s", report.id)
        report.research_status = CompanyResearchStatus.failed.value
        report.research_completed_at = utc_now()
        report.generation_error = "公司情报检索失败：公司名称为空，待人工审核"
        return None
    config = effective_search_config(db)
    if not config:
        report.research_status = CompanyResearchStatus.failed.value
        report.research_completed_at = utc_now()
        report.generation_error = "公司情报检索失败：联网搜索未配置，待人工审核"
        return None

    try:
        dimensions = [
            {"module_name": item.module.name, "raw_score": item.raw_score, "max_score": item.max_score, "score_rate": round(item.score_rate, 4)}
            for item in sorted(report.submission.dimension_scores, key=lambda score: score.module.sort_order)
        ]
        company = {
            "name": lead.company_name,
            "city": lead.city,
            "industry": lead.industry,
            "size": lead.company_size,
            "annual_revenue": lead.annual_revenue,
            "position": lead.position,
            "ai_focus": lead.ai_focus,
        }

        # 失败处理约定：API/网络异常与检索失败不内部重试，交给报告队列按退避
        # 重试（≤ max_attempts 次）；JSON/结构校验失败只修正一次，且复用已有
        # 搜索结果重新生成、不重新搜索，避免两层重试叠加放大调用次数。
        results: list[dict] = []
        research: dict | None = None
        last_error: str | None = None
        if config.provider == "deepseek":
            # 一步式：DeepSeek Anthropic 协议联网搜索直接输出 7 维情报 + 分析 JSON
            prompt = build_deepseek_research_prompt(company, dimensions)
            raw, machine_sources, conversation = await call_deepseek_anthropic_search(config, prompt)
            results = machine_sources
            if not raw:
                last_error = "联网检索无返回结果"
                logger.info("DeepSeek 联网检索无结果 company=%s", company_name)
            elif not machine_sources:
                last_error = "本次搜索没有可核验的 HTTP(S) 引用"
                logger.info("DeepSeek 联网检索无机器引用 company=%s", company_name)
            else:
                research = parse_research_response(raw)
                structure_errors = _structure_errors(research, machine_sources)
                if structure_errors:
                    logger.warning("公司情报结构校验失败 report_id=%s: %s", report.id, "；".join(structure_errors))
                    research, corrected_errors = await _correct_deepseek_research(
                        config, prompt, conversation, machine_sources, structure_errors
                    )
                    if research is None:
                        last_error = "模型未按动态小标题结构输出：" + "；".join(corrected_errors or structure_errors)
        else:
            search_target = " ".join(
                item for item in [company_name, (lead.city or "").strip(), (lead.industry or "").strip()] if item
            )
            results = await search_company_web(config, search_target)
            if not results:
                last_error = "网页检索无结果"
                logger.info("公司情报检索无结果 company=%s", company_name)
            else:
                search_text = format_search_results(results)
                prompt = build_research_prompt(company, search_text, dimensions)
                llm_override = effective_llm_override(db)
                raw = await _chat_completion(
                    "你是严谨的企业情报与 AI 转型分析助手，输出必须为合法 JSON。",
                    prompt,
                    llm_override,
                )
                if not raw:
                    last_error = "情报模型无返回"
                else:
                    research = parse_research_response(raw)
                    structure_errors = _structure_errors(research, results)
                    if structure_errors:
                        logger.warning("公司情报结构校验失败 report_id=%s: %s", report.id, "；".join(structure_errors))
                        research, corrected_errors = await _correct_external_research(
                            prompt, results, structure_errors, llm_override
                        )
                        if research is None:
                            last_error = "模型未按动态小标题结构输出：" + "；".join(corrected_errors or structure_errors)

        if research is None:
            if last_error:
                report.generation_error = f"公司情报检索失败：{last_error}"
                logger.warning("公司情报检索最终失败 report_id=%s: %s", report.id, last_error)
            report.research_status = CompanyResearchStatus.failed.value
            report.research_completed_at = utc_now()
            return None
    except Exception as exc:  # noqa: BLE001
        # 异常不做内部重试：写入失败原因后由报告队列按退避重试（≤ max_attempts）。
        logger.warning("公司情报检索失败 report_id=%s: %s", report.id, exc)
        report.research_status = CompanyResearchStatus.failed.value
        report.research_completed_at = utc_now()
        report.generation_error = f"公司情报检索失败：{type(exc).__name__}: {exc}"
        return None

    research.setdefault("company_name", company_name)
    research["evidence_version"] = 1
    research["researched_at"] = utc_now().isoformat()
    report.company_research_json = json.dumps(research, ensure_ascii=False)
    report.research_status = CompanyResearchStatus.generated.value
    report.research_completed_at = utc_now()
    report.generation_error = None
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
        value = research.get(key)
        text = research_section_text(value)
        if not text:
            continue
        subsections = research_subsections(value)
        if subsections:
            content = "".join(
                f"<h4>{escape(item['title'])}</h4><p>{escape(item['content']).replace(chr(10), '<br>')}</p>"
                for item in subsections
            )
        else:
            content = f"<p>{escape(text).replace(chr(10), '<br>')}</p>"
        source_note = ""
        if key in FACTUAL_SECTION_KEYS:
            indices = research_source_indices(research, key)
            if indices:
                source_note = '<p class="company-research-sources">资料来源：' + " ".join(
                    f"[来源{index}]" for index in indices
                ) + "</p>"
            elif value == MISSING_RESEARCH:
                source_note = '<p class="company-research-sources">资料来源：暂未检索到可靠公开信息</p>'
            else:
                source_note = '<p class="company-research-sources">资料来源：证据校验失败，未找到可核验来源编号</p>'
        blocks.append(f"<h3>{escape(label)}</h3>{content}{source_note}")
    analysis_value = research.get(ANALYSIS_KEY)
    analysis = research_section_text(analysis_value)
    analysis_sections = research_subsections(analysis_value)
    if analysis_sections:
        analysis_body = "".join(
            f"<h4>{escape(item['title'])}</h4><p>{escape(item['content']).replace(chr(10), '<br>')}</p>"
            for item in analysis_sections
        )
    else:
        analysis_body = f"<p>{escape(analysis).replace(chr(10), '<br>')}</p>" if analysis else ""
    analysis_html = f"<h3>AI 综合分析</h3>{analysis_body}" if analysis_body else ""
    sources = research.get("sources") or []
    safe_sources = [
        (index, source, normalize_source_url(source.get("url")))
        for index, source in enumerate(sources, 1)
        if isinstance(source, dict) and normalize_source_url(source.get("url")) is not None
    ]
    source_items = "".join(
        f'<li><span>[来源{index}]</span> <a href="{escape(url or "")}" target="_blank" rel="noopener noreferrer">{escape(str(source.get("title") or url or ""))}</a></li>'
        for index, source, url in safe_sources
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

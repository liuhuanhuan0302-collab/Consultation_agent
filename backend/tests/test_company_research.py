import asyncio
import http.server
import json
import threading

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin import api_gateway as gateway_endpoint
from app.api.v1.endpoints.admin.api_gateway import update_llm_config, update_search_config
from app.config import Settings
from app.database import Base
from app.models import CompanyLead, DiagnosisSubmission, GatewayApiConfig, OperationLog, Report, Role, User
from app.schemas import LlmConfigUpdate, LlmTestRequest, SearchConfigUpdate
from app.service import api_gateway_service, company_research
from app.service.api_gateway_service import (
    LlmGatewayOverride,
    SearchGatewayConfig,
    decrypt_secret,
    encrypt_secret,
    get_gateway_config,
    mask_key,
    migrate_gateway_secrets,
    validate_gateway_url,
)
from app.service.company_research import (
    build_deepseek_research_prompt,
    build_research_fix_prompt,
    build_research_prompt,
    call_deepseek_anthropic_search,
    format_search_results,
    parse_anthropic_response_blocks,
    parse_research_response,
    research_section_text,
    research_subsections,
    render_company_research_html,
    research_company,
    trusted_research_sources,
    validate_structured_research,
)


def create_db() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def create_admin(db: Session) -> User:
    user = User(email="admin@example.com", name="Admin", role=Role.admin.value, password_hash="hash")
    db.add(user)
    db.flush()
    return user


# ── 纯函数 ──────────────────────────────────────────────────────────


def structured_research_payload() -> dict:
    section = [{"title": "经营定位", "content": "公开信息摘要"}, {"title": "业务特征", "content": "业务情况摘要"}]
    return {
        "company_overview": section,
        "revenue_scale": section,
        "products": section,
        "industry_characteristics": section,
        "development_status": section,
        "challenges": section,
        "ai_opportunities": section,
        "analysis": [{"title": "综合判断", "content": "诊断结论"}, {"title": "行动建议", "content": "优先建议"}],
        "sources": [{"title": "官网", "url": "https://example.com"}],
        "source_refs": {
            "company_overview": [1],
            "revenue_scale": [1],
            "products": [1],
            "industry_characteristics": [1],
            "development_status": [1],
        },
    }

def test_parse_research_response_plain_json():
    text = '{"company_overview": "介绍", "analysis": "分析", "sources": [{"title": "t", "url": "https://a"}]}'
    parsed = parse_research_response(text)
    assert parsed["company_overview"] == "介绍"
    assert parsed["analysis"] == "分析"


def test_parse_research_response_markdown_fenced():
    text = '```json\n{"company_overview": "介绍"}\n```'
    assert parse_research_response(text)["company_overview"] == "介绍"


def test_parse_research_response_bad_json_returns_none():
    assert parse_research_response("这不是 JSON") is None
    assert parse_research_response("") is None


def test_structured_research_helpers_preserve_legacy_and_validate_new_shape():
    payload = structured_research_payload()
    assert validate_structured_research(payload) == []
    assert research_subsections(payload["company_overview"])[0]["title"] == "经营定位"
    assert "经营定位：公开信息摘要" in research_section_text(payload["company_overview"])
    assert research_section_text("历史情报正文") == "历史情报正文"
    assert validate_structured_research({"company_overview": "旧格式"})


def test_validate_research_rejects_source_problems():
    payload = structured_research_payload()
    payload.pop("sources")
    assert validate_structured_research(payload)

    payload = structured_research_payload()
    payload["sources"] = []
    assert validate_structured_research(payload)

    payload = structured_research_payload()
    payload["sources"] = [{"title": "缺少 url"}]
    assert validate_structured_research(payload)

    # source_refs 越界（sources 只有 1 条，序号 5 不存在）
    payload = structured_research_payload()
    payload["source_refs"] = {"company_overview": [1, 5]}
    assert validate_structured_research(payload)

    payload = structured_research_payload()
    payload.pop("source_refs")
    assert validate_structured_research(payload)

    payload = structured_research_payload()
    payload["source_refs"]["unknown_section"] = [1]
    assert validate_structured_research(payload)

    payload = structured_research_payload()
    payload["source_refs"]["products"] = []
    assert validate_structured_research(payload)

    payload = structured_research_payload()
    payload["source_refs"]["products"] = [1, 1]
    assert validate_structured_research(payload)

    for invalid_index in [True, "1", 0, -1, {"index": 1}]:
        payload = structured_research_payload()
        payload["source_refs"]["products"] = [invalid_index]
        assert validate_structured_research(payload)

    payload = structured_research_payload()
    payload["sources"][0]["url"] = "javascript:alert(1)"
    assert validate_structured_research(payload)


def test_reconcile_sources_only_accepts_current_search_citations():
    research = structured_research_payload()
    research["sources"] = [
        {"title": "模型标题", "url": "HTTPS://EXAMPLE.COM:443/path/#fragment"},
        {"title": "重复来源", "url": "https://example.com/path"},
    ]
    for key in research["source_refs"]:
        research["source_refs"][key] = [2]

    errors = company_research.reconcile_research_sources(
        research,
        [{"title": "真实搜索标题", "url": "https://example.com/path/", "snippet": "x"}],
    )

    assert errors == []
    assert research["sources"] == [{"title": "真实搜索标题", "url": "https://example.com/path"}]
    assert research["source_refs"]["company_overview"] == [1]
    assert validate_structured_research(research) == []


def test_reconcile_sources_rejects_invented_or_missing_model_sources():
    research = structured_research_payload()
    research["sources"] = [{"title": "伪造", "url": "https://invented.example"}]
    citations = [{"title": "真实官网", "url": "https://real.example"}]
    assert company_research.reconcile_research_sources(research, citations)

    research = structured_research_payload()
    research["sources"] = []
    assert company_research.reconcile_research_sources(research, citations)


def test_reconcile_does_not_hide_duplicate_source_references():
    research = structured_research_payload()
    research["source_refs"]["products"] = [1, 1]
    assert company_research.reconcile_research_sources(
        research,
        [{"title": "官网", "url": "https://example.com"}],
    ) == []
    assert research["source_refs"]["products"] == [1, 1]
    assert validate_structured_research(research)


def test_build_research_prompt_contains_company_and_dimensions():
    prompt = build_research_prompt(
        {"name": "测试公司", "industry": "制造业"},
        "[1] 标题\n    摘要\n    https://example.com",
        [{"module_name": "数据治理", "raw_score": 10, "max_score": 28, "score_rate": 0.3571}],
    )
    assert "测试公司" in prompt
    assert "数据治理" in prompt
    assert "营收规模" in prompt
    assert "analysis" in prompt
    assert "动态生成 2-5 个小标题" in prompt


def test_format_search_results_limits_length():
    results = [{"title": f"标题{i}", "snippet": "x" * 500, "url": f"https://e.com/{i}"} for i in range(200)]
    text = format_search_results(results, limit=2000)
    assert len(text) <= 2500
    assert "[1]" in text


def test_render_company_research_html_contains_sections_and_sources():
    research = {
        "company_overview": "一家公司",
        "revenue_scale": "公开渠道未披露",
        "analysis": "建议做 AI 试点",
        "sources": [{"title": "官网", "url": "https://example.com"}],
    }
    html = render_company_research_html(research)
    assert "企业画像与转型分析" in html
    assert "公司介绍" in html
    assert "AI 综合分析" in html
    assert "https://example.com" in html
    assert "建议做 AI 试点" in html


def test_render_company_research_html_renders_dynamic_subheadings():
    research = structured_research_payload()
    html = render_company_research_html(research)
    assert "<h4>经营定位</h4>" in html
    assert "<h4>行动建议</h4>" in html
    assert "资料来源：[来源1]" in html
    assert "<span>[来源1]</span>" in html
    assert "见本部分信息来源清单" not in html


def test_render_company_research_html_escapes_script():
    research = {"company_overview": "<script>alert(1)</script>", "analysis": "x"}
    html = render_company_research_html(research)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_company_research_html_exposes_missing_refs_and_blocks_unsafe_historical_url():
    research = structured_research_payload()
    research["source_refs"].pop("products")
    research["sources"][0]["url"] = "javascript:alert(1)"
    html = render_company_research_html(research)
    assert "资料来源：证据校验失败，未找到可核验来源编号" in html
    assert "javascript:" not in html


def test_mask_key():
    assert mask_key(None) == ""
    assert mask_key("short") == "***"
    assert mask_key("sk-abcdef123456") == "sk-***456"


# ── 网关地址安全校验 ──────────────────────────────────────────────

def test_validate_gateway_url_rejects_unsafe_targets():
    unsafe = [
        "http://api.bochaai.com/v1",  # 非 HTTPS
        "https://127.0.0.1",
        "https://10.0.0.5",
        "https://192.168.1.1",
        "https://169.254.169.254",  # 云元数据地址
        "https://localhost",
        "https://metadata.google.internal",
        "https://example.com:8443",  # 非标准端口
    ]
    for url in unsafe:
        try:
            validate_gateway_url(url)
            raise AssertionError(f"应当拒绝 {url}")
        except ValueError:
            pass


def test_validate_gateway_url_rejects_dns_rebinding(monkeypatch):
    """域名解析到私网地址（DNS 重绑定）必须拒绝。"""
    monkeypatch.setattr(
        api_gateway_service.socket,
        "getaddrinfo",
        lambda host, port, proto: [(0, 0, 0, "", ("127.0.0.1", 443))],
    )
    try:
        validate_gateway_url("https://evil.example.com")
        raise AssertionError("应当拒绝解析到私网地址的域名")
    except ValueError:
        pass


def test_validate_gateway_url_accepts_public_https(monkeypatch):
    monkeypatch.setattr(
        api_gateway_service.socket,
        "getaddrinfo",
        lambda host, port, proto: [(0, 0, 0, "", ("93.184.216.34", 443))],
    )
    assert validate_gateway_url("https://api.example.com/v1") == "https://api.example.com/v1"


# ── 密钥加密与轮换 ────────────────────────────────────────────────

def test_secret_encryption_roundtrip_and_rotation(monkeypatch):
    monkeypatch.setattr(api_gateway_service, "get_settings", lambda: Settings(secret_key="key-a", _env_file=None))
    token = encrypt_secret("sk-secret123456")
    assert "sk-secret123456" not in token
    assert token.startswith("enc:v1:")
    assert decrypt_secret(token) == "sk-secret123456"

    # 轮换密钥后旧密文无法解密，视为未配置，管理员需重新填写
    monkeypatch.setattr(api_gateway_service, "get_settings", lambda: Settings(secret_key="key-b", _env_file=None))
    assert decrypt_secret(token) is None
    assert decrypt_secret("sk-plain-legacy") == "sk-plain-legacy"  # 历史明文兼容


# ── 网关配置接口 ────────────────────────────────────────────────────

def test_gateway_update_encrypts_key_and_masks_response():
    db, engine = create_db()
    user = create_admin(db)
    db.commit()

    updated = update_search_config(
        SearchConfigUpdate(search_provider="bocha", search_api_key="sk-abcdef123456"),
        db=db,
        user=user,
    )
    assert updated.search_api_key == "sk-***456"

    config = get_gateway_config(db)
    assert "sk-abcdef123456" not in config.search_api_key  # 密文入库
    assert decrypt_secret(config.search_api_key) == "sk-abcdef123456"

    # key 留空 = 保留原值
    update_search_config(
        SearchConfigUpdate(search_provider="bocha", search_api_key=""),
        db=db,
        user=user,
    )
    config = get_gateway_config(db)
    assert decrypt_secret(config.search_api_key) == "sk-abcdef123456"
    db.close()
    engine.dispose()


def test_gateway_update_rejects_bad_provider_and_url():
    db, engine = create_db()
    user = create_admin(db)
    db.commit()

    try:
        update_search_config(SearchConfigUpdate(search_provider="unknown"), db=db, user=user)
        raise AssertionError("应当拒绝未知 provider")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422

    try:
        update_search_config(SearchConfigUpdate(search_base_url="http://evil.example.com"), db=db, user=user)
        raise AssertionError("应当拒绝 http 地址")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    db.close()
    engine.dispose()


def test_put_switching_to_custom_requires_new_key():
    """切换 Bocha → custom 且未填新 Key：422，不能复用数据库已有 Key。"""
    db, engine = create_db()
    user = create_admin(db)
    db.commit()
    update_search_config(
        SearchConfigUpdate(search_provider="bocha", search_api_key="sk-saved-key"),
        db=db,
        user=user,
    )
    try:
        update_search_config(
            SearchConfigUpdate(search_provider="custom", search_api_key="", search_base_url="https://search.example.com"),
            db=db,
            user=user,
        )
        raise AssertionError("应当拒绝：切换 custom 未提供新 Key")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    db.close()
    engine.dispose()


def test_put_builtin_provider_rejects_custom_base_url():
    """内置服务商传自定义（攻击者）公网 HTTPS 地址：422。"""
    db, engine = create_db()
    user = create_admin(db)
    db.commit()
    try:
        update_search_config(
            SearchConfigUpdate(search_provider="bocha", search_api_key="sk-new-key", search_base_url="https://attacker.example.com"),
            db=db,
            user=user,
        )
        raise AssertionError("应当拒绝：内置服务商不允许自定义地址")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    db.close()
    engine.dispose()


def test_put_llm_base_change_requires_new_key():
    """更换 LLM 接口地址且尝试沿用已保存 Key：422。"""
    db, engine = create_db()
    user = create_admin(db)
    db.commit()
    try:
        update_llm_config(
            LlmConfigUpdate(llm_base_url="https://api.deepseek.com", llm_api_key=""),
            db=db,
            user=user,
        )
        raise AssertionError("应当拒绝：更换 LLM 地址未提供新 Key")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    db.close()
    engine.dispose()


def test_migrate_gateway_secrets_encrypts_legacy_plaintext():
    """历史明文 Key 启动迁移后变为 enc:v1: 密文，可正确解密，且审计日志不含密钥内容。"""
    db, engine = create_db()
    config = GatewayApiConfig(
        id=1,
        search_enabled=True,
        search_provider="bocha",
        search_api_key="sk-plain-search",
        llm_api_key="sk-plain-llm",
    )
    db.add(config)
    db.commit()

    migrate_gateway_secrets(db)

    migrated = db.get(GatewayApiConfig, 1)
    assert migrated.search_api_key.startswith("enc:v1:")
    assert migrated.llm_api_key.startswith("enc:v1:")
    assert decrypt_secret(migrated.search_api_key) == "sk-plain-search"
    assert decrypt_secret(migrated.llm_api_key) == "sk-plain-llm"

    log = db.query(OperationLog).filter(OperationLog.action == "gateway_secrets_migrated").first()
    assert log is not None
    assert "sk-plain" not in (log.detail_json or "")
    db.close()
    engine.dispose()


def test_custom_search_does_not_follow_redirects():
    """custom 搜索不跟随 30x 重定向：重定向目标（私网地址）不应被请求。"""
    reached_target = {"value": False}

    class RedirectHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/secret"):
                reached_target["value"] = True
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"results": []}')
            else:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_address[1]}/secret")
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        config = SearchGatewayConfig(
            provider="custom",
            api_key="k",
            base_url=f"http://127.0.0.1:{port}",
            timeout_seconds=5,
            max_results=3,
        )
        try:
            asyncio.run(company_research.search_single_query(config, "测试"))
        except Exception:
            pass  # 302 空响应体解析失败即证明未跟随重定向
        else:
            raise AssertionError("重定向响应应导致调用失败")
        assert reached_target["value"] is False
    finally:
        server.shutdown()
        thread.join(timeout=5)


# ── 搜索结果数量上限 ──────────────────────────────────────────────

def test_search_company_web_respects_max_results(monkeypatch):
    config = SearchGatewayConfig(
        provider="bocha",
        api_key="k",
        base_url="https://api.bochaai.com/v1",
        timeout_seconds=5,
        max_results=3,
    )
    counts: list[int] = []

    async def fake_search(client, cfg, query, count):
        counts.append(count)
        return [{"title": f"t{i}", "snippet": "s", "url": f"https://e.com/{i}"} for i in range(count)]

    monkeypatch.setattr(company_research, "_search_once", fake_search)
    results = asyncio.run(company_research.search_company_web(config, "测试公司"))

    assert len(results) == 3
    assert counts and all(count == 3 for count in counts)


# ── P1：轮换密钥后禁止把 .env Key 发往网关保存的自定义 LLM 地址 ─────

def test_chat_completion_blocks_env_key_for_gateway_base(monkeypatch):
    """网关有自定义 LLM 地址但网关 Key 不可用：跳过调用，不得使用 .env Key。"""
    monkeypatch.setattr(company_research, "get_settings", lambda: Settings(deepseek_api_key="sk-env-key", _env_file=None))

    class ExplodingClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("不应发起任何网络请求")

    monkeypatch.setattr(company_research.httpx, "AsyncClient", ExplodingClient)
    result = asyncio.run(
        company_research._chat_completion(
            "s",
            "u",
            LlmGatewayOverride(api_key=None, base_url="https://llm.example.com", model=None),
        )
    )
    assert result is None


def test_llm_test_blocks_env_key_when_gateway_base_without_key(monkeypatch):
    """测试接口同样禁止：已保存自定义地址 + 网关 Key 无法解密 → 提示重新录入。"""
    db, engine = create_db()
    user = create_admin(db)
    db.commit()

    monkeypatch.setattr(api_gateway_service, "get_settings", lambda: Settings(secret_key="key-a", _env_file=None))
    config = get_gateway_config(db)
    config.llm_base_url = "https://llm.example.com"
    config.llm_api_key = encrypt_secret("sk-gateway-key")
    db.commit()

    # 轮换密钥：网关 Key 无法解密，.env 里有 Key
    rotated = lambda: Settings(secret_key="key-b", _env_file=None, deepseek_api_key="sk-env-key")
    monkeypatch.setattr(api_gateway_service, "get_settings", rotated)
    monkeypatch.setattr(gateway_endpoint, "get_settings", rotated)

    result = asyncio.run(gateway_endpoint.test_llm_gateway(LlmTestRequest(), db=db, user=user))
    assert result["ok"] is False
    assert "无法解密" in result["error"]
    db.close()
    engine.dispose()


# ── DeepSeek 联网搜索服务商适配（Anthropic 协议） ────────────────────


def anthropic_response_fixture(stop_reason: str = "end_turn") -> dict:
    """按真实 DeepSeek /anthropic/v1/messages 响应结构构造的 fixture：
    thinking → server_tool_use → web_search_tool_result → text 块序列。"""
    return {
        "id": "msg_x",
        "type": "message",
        "role": "assistant",
        "model": "deepseek-v4-flash",
        "stop_reason": stop_reason,
        "content": [
            {"type": "thinking", "thinking": "先核实公司背景", "signature": "sig"},
            {
                "type": "server_tool_use",
                "id": "call_00_x",
                "name": "web_search",
                "caller": "system",
                "input": {"query": "可孚医疗科技股份有限公司 主要信息"},
            },
            {
                "type": "web_search_tool_result",
                "tool_use_id": "call_00_x",
                "content": [
                    {
                        "type": "web_search_result",
                        "title": "长沙雨花区企业可孚医疗登陆港交所",
                        "url": "https://finance.sina.cn/2026-05-07/detail-inhxahrf8343938.d.html?vt=4",
                        "page_age": "2026-05-07",
                        "encrypted_content": "密文占位",
                    },
                    {
                        "type": "web_search_result",
                        "title": "可孚医疗登陆港交所，A+H双平台打开全球化新空间",
                        "url": "https://www.ceweekly.cn/company/2026/0507/493787.html",
                        "page_age": "2026-05-07",
                        "encrypted_content": "密文占位",
                    },
                ],
            },
            {
                "type": "text",
                "text": "根据联网搜索结果，可孚医疗是……详情见 https://model-made-up.example.com/a",
            },
        ],
    }


def test_parse_anthropic_blocks_extracts_machine_sources_only():
    text_parts, sources, blocks = parse_anthropic_response_blocks(anthropic_response_fixture())

    assert "根据联网搜索结果" in "\n".join(text_parts)
    assert len(sources) == 2
    assert sources[0]["title"] == "长沙雨花区企业可孚医疗登陆港交所"
    assert sources[0]["url"] == "https://finance.sina.cn/2026-05-07/detail-inhxahrf8343938.d.html?vt=4"
    assert sources[1]["url"] == "https://www.ceweekly.cn/company/2026/0507/493787.html"
    # thinking / server_tool_use 块与正文中的 URL 都不是机器引用
    assert all(source["url"] != "https://model-made-up.example.com/a" for source in sources)
    assert blocks == anthropic_response_fixture()["content"]


def test_trusted_sources_dedup_repeated_search_results():
    """多个 web_search_tool_result 块重复返回同一 URL 时只保留一条。"""
    fixture = anthropic_response_fixture()
    duplicate_block = {
        "type": "web_search_tool_result",
        "tool_use_id": "call_01_y",
        "content": [
            {
                "type": "web_search_result",
                "title": "同一来源再次出现",
                "url": "https://finance.sina.cn/2026-05-07/detail-inhxahrf8343938.d.html?vt=4&wm=1",
                "encrypted_content": "密文占位",
            }
        ],
    }
    fixture["content"].append(duplicate_block)
    _, sources, _ = parse_anthropic_response_blocks(fixture)

    trusted = trusted_research_sources(sources)
    assert len(trusted) == 2
    urls = {source["url"] for source in trusted}
    assert "https://finance.sina.cn/2026-05-07/detail-inhxahrf8343938.d.html" in urls
    assert "https://www.ceweekly.cn/company/2026/0507/493787.html" in urls


def test_build_research_fix_prompt_lists_trusted_urls():
    fix = build_research_fix_prompt(["模型输出 JSON 解析失败"], [{"title": "t", "url": "https://real.example/a"}])
    assert "JSON 解析失败" in fix
    assert "https://real.example/a" in fix
    assert "web_search_tool_result" in fix


def test_build_deepseek_research_prompt_requests_web_search():
    prompt = build_deepseek_research_prompt(
        {"name": "测试公司", "industry": "制造业"},
        [{"module_name": "数据治理", "raw_score": 10, "max_score": 28, "score_rate": 0.3571}],
    )
    assert "web_search" in prompt
    assert "测试公司" in prompt
    assert "数据治理" in prompt
    assert "sources" in prompt


def test_deepseek_provider_rejects_custom_base_url():
    db, engine = create_db()
    user = create_admin(db)
    db.commit()
    try:
        update_search_config(
            SearchConfigUpdate(search_provider="deepseek", search_api_key="sk-new-key", search_base_url="https://attacker.example.com"),
            db=db,
            user=user,
        )
        raise AssertionError("应当拒绝：DeepSeek 内置服务商不允许自定义地址")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    db.close()
    engine.dispose()


def test_research_company_deepseek_one_shot(monkeypatch):
    """DeepSeek 服务商：一次调用完成检索 + 情报 JSON，无需外部搜索 API。"""
    from app.models import AiConversationMessage, CompanyLead, DiagnosisSubmission, Report, ReportStatus

    db, engine = create_db()
    lead = CompanyLead(company_name="江苏芯云电子科技有限公司", industry="芯片")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="T", html_content="", status=ReportStatus.pending.value, generation_error="旧错误应被清除")
    db.add(report)
    db.commit()

    monkeypatch.setattr(api_gateway_service, "get_settings", lambda: Settings(secret_key="key-a", _env_file=None))
    config = get_gateway_config(db)
    config.search_enabled = True
    config.search_provider = "deepseek"
    config.search_api_key = encrypt_secret("sk-deepseek-key")
    db.commit()

    async def fake_anthropic_search(cfg, prompt, **kwargs):
        assert cfg.provider == "deepseek"
        assert "江苏芯云电子科技有限公司" in prompt
        return (
            json.dumps(structured_research_payload(), ensure_ascii=False),
            [{"title": "官网", "url": "https://example.com", "snippet": ""}],
            [{"role": "user", "content": prompt}],
        )

    monkeypatch.setattr(company_research, "call_deepseek_anthropic_search", fake_anthropic_search)
    result = asyncio.run(research_company(db, report))

    assert result is not None
    assert result["company_overview"][0]["title"] == "经营定位"
    assert report.company_research_json is not None
    assert report.generation_error is None  # 进入处理状态与成功时旧错误被清除
    message = db.query(AiConversationMessage).filter(AiConversationMessage.purpose == "company_research").first()
    assert message is not None
    assert '"provider": "deepseek"' in (message.metadata_json or "")
    db.close()
    engine.dispose()


def test_research_rejects_empty_model_sources_even_with_citations(monkeypatch):
    """空 sources 无法证明 source_refs 映射关系，重试后必须失败关闭。"""
    from app.models import CompanyLead, DiagnosisSubmission, Report, ReportStatus

    db, engine = create_db()
    lead = CompanyLead(company_name="江苏芯云电子科技有限公司", industry="芯片")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="T", html_content="", status=ReportStatus.pending.value)
    db.add(report)
    db.commit()

    monkeypatch.setattr(api_gateway_service, "get_settings", lambda: Settings(secret_key="key-a", _env_file=None))
    config = get_gateway_config(db)
    config.search_enabled = True
    config.search_provider = "deepseek"
    config.search_api_key = encrypt_secret("sk-deepseek-key")
    db.commit()

    payload = structured_research_payload()
    payload["sources"] = []  # 模型主动返回空来源
    calls = []

    async def fake_anthropic_search(cfg, prompt, **kwargs):
        calls.append(kwargs)
        return (
            json.dumps(payload, ensure_ascii=False),
            [{"title": "真实官网", "url": "https://real.example", "snippet": ""}],
            [{"role": "user", "content": prompt}],
        )

    monkeypatch.setattr(company_research, "call_deepseek_anthropic_search", fake_anthropic_search)
    result = asyncio.run(research_company(db, report))

    assert result is None
    assert report.company_research_json is None
    assert report.research_status == company_research.CompanyResearchStatus.failed.value
    assert "sources 缺失或为空" in (report.generation_error or "")
    # 只修正一次，且修正轮复用已有搜索结果（不带搜索工具，不重新搜索）
    assert len(calls) == 2
    assert calls[1].get("with_search_tool") is False
    assert "sources 缺失或为空" in calls[1].get("follow_up_user", "")
    db.close()
    engine.dispose()


def test_research_rejects_model_url_without_machine_citations(monkeypatch):
    """模型正文/JSON 自报的 URL 不能成为可信搜索引用。"""
    from app.models import CompanyLead, DiagnosisSubmission, Report

    db, engine = create_db()
    lead = CompanyLead(company_name="证据测试公司", industry="软件")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="T", html_content="")
    db.add(report)
    db.commit()

    config = SearchGatewayConfig(
        provider="deepseek",
        api_key="k",
        base_url="https://api.deepseek.com",
        timeout_seconds=10,
        max_results=5,
        model="m",
    )
    raw = json.dumps(structured_research_payload(), ensure_ascii=False)
    calls = []

    async def fake_search(_cfg, _prompt, **kwargs):
        calls.append(kwargs)
        return raw, [], []

    monkeypatch.setattr(company_research, "effective_search_config", lambda _db: config)
    monkeypatch.setattr(company_research, "call_deepseek_anthropic_search", fake_search)
    result = asyncio.run(research_company(db, report))

    assert result is None
    assert report.research_status == company_research.CompanyResearchStatus.failed.value
    assert "没有可核验" in (report.generation_error or "")
    assert len(calls) == 1  # 无机器引用时不修正、不重新搜索，交队列退避重试
    db.close()
    engine.dispose()


def test_deepseek_search_uses_shared_env_key_and_ignores_legacy_disabled_flag(monkeypatch):
    db, engine = create_db()
    config = get_gateway_config(db)
    config.search_enabled = False
    config.search_provider = "deepseek"
    config.search_api_key = None
    db.commit()
    monkeypatch.setattr(
        api_gateway_service,
        "get_settings",
        lambda: Settings(deepseek_api_key="sk-shared-env", _env_file=None),
    )

    effective = api_gateway_service.effective_search_config(db)

    assert effective is not None
    assert effective.provider == "deepseek"
    assert effective.api_key == "sk-shared-env"
    assert effective.model == api_gateway_service.DEFAULT_DEEPSEEK_SEARCH_MODEL
    db.close()
    engine.dispose()


def test_effective_search_config_refuses_env_key_with_custom_base(monkeypatch):
    """deepseek 服务商配置了自定义搜索地址、但网关 Key 不可用（解密失败）时，
    不得把 .env 的 DeepSeek Key 发往该地址，应视为未配置。"""
    db, engine = create_db()
    config = get_gateway_config(db)
    config.search_provider = "deepseek"
    config.search_base_url = "https://search-gateway.example/v1"
    config.search_api_key = None
    db.commit()
    monkeypatch.setattr(
        api_gateway_service,
        "get_settings",
        lambda: Settings(deepseek_api_key="sk-shared-env", _env_file=None),
    )

    assert api_gateway_service.effective_search_config(db) is None
    db.close()
    engine.dispose()


def test_research_short_company_name_is_not_skipped(monkeypatch):
    """两字公司名（如“华为”）同样应执行检索，而不是被长度门槛静默跳过。"""
    db, engine = create_db()
    lead = CompanyLead(company_name="华为", industry="制造业")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="T", html_content="")
    db.add(report)
    db.commit()

    raw = json.dumps(structured_research_payload(), ensure_ascii=False)
    config = SearchGatewayConfig(
        provider="deepseek",
        api_key="k",
        base_url="https://api.deepseek.com",
        timeout_seconds=10,
        max_results=5,
        model="m",
    )

    async def fake_search(_cfg, _prompt, **kwargs):
        return raw, [{"title": "t", "snippet": "", "url": "https://example.com"}], []

    monkeypatch.setattr(company_research, "effective_search_config", lambda _db: config)
    monkeypatch.setattr(company_research, "call_deepseek_anthropic_search", fake_search)

    result = asyncio.run(research_company(db, report))

    assert result is not None
    assert result["company_name"] == "华为"
    db.close()
    engine.dispose()


# ── Anthropic 协议行为与重试语义 ─────────────────────────────────────


class _FakeAnthropicResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAnthropicClient:
    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append(json)
        return _FakeAnthropicResponse(self._payloads.pop(0))


def test_anthropic_pause_turn_continuation(monkeypatch):
    """stop_reason=pause_turn 时按协议续传：assistant 内容原样追加后再次调用。"""
    first = anthropic_response_fixture(stop_reason="pause_turn")
    second = {**anthropic_response_fixture(), "content": [{"type": "text", "text": "续传后的完整答案"}]}
    client = _FakeAnthropicClient([first, second])
    monkeypatch.setattr(company_research.httpx, "AsyncClient", lambda *a, **k: client)

    config = SearchGatewayConfig(
        provider="deepseek",
        api_key="k",
        base_url="https://api.deepseek.com",
        timeout_seconds=10,
        max_results=5,
        model="deepseek-v4-flash",
    )
    text, sources, messages = asyncio.run(call_deepseek_anthropic_search(config, "检索目标公司"))

    assert "续传后的完整答案" in (text or "")
    assert sources[0]["title"] == "长沙雨花区企业可孚医疗登陆港交所"
    assert len(client.calls) == 2
    # 续传请求把第一次的 assistant 内容原样追加进消息列表
    assert client.calls[1]["messages"][-1]["role"] == "assistant"
    assert client.calls[1]["messages"][-1]["content"] == first["content"]
    # 协议续传不算失败重试：两次调用都带搜索工具
    assert client.calls[0]["tools"] and client.calls[1]["tools"]
    assert len(messages) == 2


def test_anthropic_pause_turn_exhausted_raises(monkeypatch):
    """连续 pause_turn 超过上限时放弃本次调用并抛错（交队列退避重试）。"""
    client = _FakeAnthropicClient([anthropic_response_fixture("pause_turn") for _ in range(3)])
    monkeypatch.setattr(company_research.httpx, "AsyncClient", lambda *a, **k: client)

    config = SearchGatewayConfig(
        provider="deepseek",
        api_key="k",
        base_url="https://api.deepseek.com",
        timeout_seconds=10,
        max_results=5,
        model="deepseek-v4-flash",
    )
    with pytest.raises(RuntimeError, match="pause_turn"):
        asyncio.run(call_deepseek_anthropic_search(config, "检索目标公司"))
    assert len(client.calls) == 3


def test_research_json_parse_failure_corrected_once_reusing_results(monkeypatch):
    """JSON 解析失败：同一队列任务内修正一次，复用机器搜索结果、不重新搜索。"""
    db, engine = create_db()
    lead = CompanyLead(company_name="修正测试公司", industry="软件")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="T", html_content="")
    db.add(report)
    db.commit()

    config = SearchGatewayConfig(
        provider="deepseek",
        api_key="k",
        base_url="https://api.deepseek.com",
        timeout_seconds=10,
        max_results=5,
        model="m",
    )
    citations = [{"title": "官网", "url": "https://example.com", "snippet": ""}]
    calls = []

    async def fake_search(_cfg, _prompt, **kwargs):
        calls.append(kwargs)
        payload = "这不是合法 JSON {"
        if kwargs.get("follow_up_user"):
            payload = json.dumps(structured_research_payload(), ensure_ascii=False)
        return payload, citations, [{"role": "user", "content": "历史对话"}]

    monkeypatch.setattr(company_research, "effective_search_config", lambda _db: config)
    monkeypatch.setattr(company_research, "call_deepseek_anthropic_search", fake_search)

    result = asyncio.run(research_company(db, report))

    assert result is not None
    assert result["company_overview"][0]["title"] == "经营定位"
    assert len(calls) == 2
    # 修正轮：复用已有搜索结果（不带搜索工具），提示包含解析失败原因
    assert calls[1].get("with_search_tool") is False
    assert "JSON 解析失败" in calls[1].get("follow_up_user", "")
    assert calls[1].get("conversation") == [{"role": "user", "content": "历史对话"}]
    db.close()
    engine.dispose()


def test_research_api_error_not_retried_internally(monkeypatch):
    """API/网络异常不内部重试：一次失败即交报告队列退避重试，避免 3×3 放大。"""
    db, engine = create_db()
    lead = CompanyLead(company_name="异常测试公司", industry="软件")
    db.add(lead)
    db.flush()
    submission = DiagnosisSubmission(lead_id=lead.id)
    db.add(submission)
    db.flush()
    report = Report(submission_id=submission.id, title="T", html_content="", generation_error="上一轮的旧错误")
    db.add(report)
    db.commit()

    config = SearchGatewayConfig(
        provider="deepseek",
        api_key="k",
        base_url="https://api.deepseek.com",
        timeout_seconds=10,
        max_results=5,
        model="m",
    )
    calls = []

    async def fake_search(_cfg, _prompt, **kwargs):
        calls.append(kwargs)
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(company_research, "effective_search_config", lambda _db: config)
    monkeypatch.setattr(company_research, "call_deepseek_anthropic_search", fake_search)

    result = asyncio.run(research_company(db, report))

    assert result is None
    assert len(calls) == 1  # 不内部重试，由报告队列按 max_attempts 退避重试
    assert "ConnectError" in (report.generation_error or "")
    assert "旧错误" not in (report.generation_error or "")  # 旧错误已被新错误覆盖
    db.close()
    engine.dispose()

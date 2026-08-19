import asyncio
import http.server
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.admin import api_gateway as gateway_endpoint
from app.api.v1.endpoints.admin.api_gateway import update_llm_config, update_search_config
from app.config import Settings
from app.database import Base
from app.models import GatewayApiConfig, OperationLog, Role, User
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
    build_research_prompt,
    format_search_results,
    parse_deepseek_responses,
    parse_research_response,
    render_company_research_html,
    research_company,
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


def test_render_company_research_html_escapes_script():
    research = {"company_overview": "<script>alert(1)</script>", "analysis": "x"}
    html = render_company_research_html(research)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


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
        SearchConfigUpdate(search_enabled=True, search_provider="bocha", search_api_key="sk-abcdef123456"),
        db=db,
        user=user,
    )
    assert updated.search_api_key == "sk-***456"

    config = get_gateway_config(db)
    assert "sk-abcdef123456" not in config.search_api_key  # 密文入库
    assert decrypt_secret(config.search_api_key) == "sk-abcdef123456"

    # key 留空 = 保留原值
    update_search_config(
        SearchConfigUpdate(search_enabled=True, search_provider="bocha", search_api_key=""),
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
        SearchConfigUpdate(search_enabled=True, search_provider="bocha", search_api_key="sk-saved-key"),
        db=db,
        user=user,
    )
    try:
        update_search_config(
            SearchConfigUpdate(search_enabled=True, search_provider="custom", search_api_key="", search_base_url="https://search.example.com"),
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
            SearchConfigUpdate(search_enabled=True, search_provider="bocha", search_api_key="sk-new-key", search_base_url="https://attacker.example.com"),
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


# ── DeepSeek 联网搜索服务商适配 ────────────────────────────────────

def test_parse_deepseek_responses_extracts_text_and_sources():
    # 结构 1：output_text + sources
    data = {
        "output_text": "正文内容",
        "sources": [{"title": "官网", "url": "https://example.com", "content": "摘要"}],
    }
    text, sources = parse_deepseek_responses(data)
    assert text == "正文内容"
    assert sources[0]["url"] == "https://example.com"
    assert sources[0]["title"] == "官网"
    assert sources[0]["snippet"] == "摘要"

    # 结构 2：output 消息列表 + web_search_call 的 response.results
    data = {
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": "第一段"}]},
            {"type": "web_search_call", "response": {"results": [{"title": "新闻", "url": "https://news.example.com", "summary": "概要"}]}},
        ]
    }
    text, sources = parse_deepseek_responses(data)
    assert "第一段" in text
    assert sources[0]["url"] == "https://news.example.com"

    # 结构 3：citations / annotations
    data = {"output_text": "x", "citations": [{"title": "c", "url": "https://c.example.com", "content": "y"}]}
    _, sources = parse_deepseek_responses(data)
    assert sources[0]["url"] == "https://c.example.com"

    # 结构 4：兜底从正文提取 URL
    text, sources = parse_deepseek_responses({"output_text": "见 https://fallback.example.com/a 详情"})
    assert sources[0]["url"] == "https://fallback.example.com/a"


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
            SearchConfigUpdate(search_enabled=True, search_provider="deepseek", search_api_key="sk-new-key", search_base_url="https://attacker.example.com"),
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
    report = Report(submission_id=submission.id, title="T", html_content="", status=ReportStatus.pending.value)
    db.add(report)
    db.commit()

    monkeypatch.setattr(api_gateway_service, "get_settings", lambda: Settings(secret_key="key-a", _env_file=None))
    config = get_gateway_config(db)
    config.search_enabled = True
    config.search_provider = "deepseek"
    config.search_api_key = encrypt_secret("sk-deepseek-key")
    db.commit()

    async def fake_web_search(cfg, prompt):
        assert cfg.provider == "deepseek"
        assert "江苏芯云电子科技有限公司" in prompt
        return ('{"company_overview": "一家芯片公司", "analysis": "建议试点", "sources": [{"title": "官网", "url": "https://example.com"}]}', [{"title": "官网", "url": "https://example.com", "snippet": ""}])

    monkeypatch.setattr(company_research, "call_deepseek_web_search", fake_web_search)
    result = asyncio.run(research_company(db, report))

    assert result is not None
    assert result["company_overview"] == "一家芯片公司"
    assert report.company_research_json is not None
    message = db.query(AiConversationMessage).filter(AiConversationMessage.purpose == "company_research").first()
    assert message is not None
    assert '"provider": "deepseek"' in (message.metadata_json or "")
    db.close()
    engine.dispose()

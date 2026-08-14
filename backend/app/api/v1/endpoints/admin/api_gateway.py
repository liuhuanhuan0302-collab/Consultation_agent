"""API 网关配置 — 搜索配置与大模型配置独立保存、独立测试（仅 admin 角色）。

安全策略（地址变化与密钥复用不能同时发生）：
- 内置搜索服务商（bocha/serpapi）固定官方地址，不允许自定义；
- 切换到 custom 或更换服务商时必须填写新的搜索 Key，不能沿用旧 Key；
- LLM 地址仅允许 DeepSeek 官方域名；自定义 OpenAI 兼容服务必须通过公网 HTTPS
  校验，且更换地址时必须同时填写新的 LLM Key。
"""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import GatewayApiConfig, User
from app.schemas import (
    GatewayConfigRead,
    LlmConfigUpdate,
    LlmTestRequest,
    SearchConfigUpdate,
    SearchTestRequest,
)
from app.service.api_gateway_service import (
    DEFAULT_SEARCH_BASE_URLS,
    SUPPORTED_SEARCH_PROVIDERS,
    SearchGatewayConfig,
    config_has_undecryptable_key,
    decrypt_secret,
    encrypt_secret,
    get_gateway_config,
    mask_key,
    validate_gateway_url,
    validate_llm_base_url,
)
from app.service.company_research import ping_deepseek_search, ping_llm, search_single_query
from app.utils.auth import AdminOnly
from app.utils.logging_utils import write_operation_log

router = APIRouter()


def serialize_gateway_config(config: GatewayApiConfig) -> GatewayConfigRead:
    """key 解密后掩码返回，解密失败（密钥已轮换）显示为空并提示重新录入。"""
    return GatewayConfigRead(
        search_enabled=config.search_enabled,
        search_provider=config.search_provider,
        search_api_key=mask_key(decrypt_secret(config.search_api_key)),
        search_base_url=config.search_base_url,
        search_timeout_seconds=config.search_timeout_seconds,
        search_max_results=config.search_max_results,
        search_model=config.search_model,
        llm_api_key=mask_key(decrypt_secret(config.llm_api_key)),
        llm_base_url=config.llm_base_url,
        llm_model=config.llm_model,
        key_reentry_required=config_has_undecryptable_key(config),
        updated_by=config.updated_by,
        updated_at=config.updated_at,
    )


def _resolve_search_base_url(provider: str, raw: str | None) -> str | None:
    """搜索接口地址策略：内置服务商固定官方地址并拒绝自定义；custom 必须提供合法地址。"""
    value = (raw or "").strip()
    if provider != "custom":
        if value:
            raise HTTPException(status_code=422, detail=f"{provider} 使用官方固定地址，不能自定义接口地址")
        return None  # 运行时取 DEFAULT_SEARCH_BASE_URLS
    if not value:
        raise HTTPException(status_code=422, detail="自定义服务商必须填写接口地址（https:// 公网地址）")
    try:
        return validate_gateway_url(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"接口地址无效：{exc}") from exc


# ══════════════════════════════════════════════════════════════════
# 3.17 查看网关配置（搜索 + 大模型）
# ══════════════════════════════════════════════════════════════════
@router.get("/api/admin/api-gateway", response_model=GatewayConfigRead)
def get_api_gateway_config(db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> GatewayConfigRead:
    return serialize_gateway_config(get_gateway_config(db))


# ══════════════════════════════════════════════════════════════════
# 3.17.1 独立保存搜索配置
# ══════════════════════════════════════════════════════════════════
@router.put("/api/admin/api-gateway/search", response_model=GatewayConfigRead)
def update_search_config(payload: SearchConfigUpdate, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> GatewayConfigRead:
    if payload.search_provider not in SUPPORTED_SEARCH_PROVIDERS:
        raise HTTPException(status_code=422, detail="不支持的搜索服务商")

    config = get_gateway_config(db)
    new_key = payload.search_api_key.strip()
    provider_changed = payload.search_provider != config.search_provider
    if (provider_changed or payload.search_provider == "custom") and not new_key:
        raise HTTPException(status_code=422, detail="切换搜索服务商或使用自定义服务商时，必须填写新的搜索 API Key（不能沿用旧 Key）")

    config.search_enabled = payload.search_enabled
    config.search_provider = payload.search_provider
    if new_key:
        config.search_api_key = encrypt_secret(new_key)
    config.search_base_url = _resolve_search_base_url(payload.search_provider, payload.search_base_url)
    config.search_timeout_seconds = payload.search_timeout_seconds
    config.search_max_results = payload.search_max_results
    config.search_model = payload.search_model.strip() if payload.search_model and payload.search_model.strip() else None
    config.updated_by = user.email
    write_operation_log(db, user, "update_search_config", "gateway_api_config", "1", {"provider": payload.search_provider})
    db.commit()
    db.refresh(config)
    return serialize_gateway_config(config)


# ══════════════════════════════════════════════════════════════════
# 3.17.2 独立保存大模型配置
# ══════════════════════════════════════════════════════════════════
@router.put("/api/admin/api-gateway/llm", response_model=GatewayConfigRead)
def update_llm_config(payload: LlmConfigUpdate, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> GatewayConfigRead:
    config = get_gateway_config(db)
    new_key = payload.llm_api_key.strip()
    new_base = payload.llm_base_url.strip() if payload.llm_base_url else ""
    base_changed = new_base != (config.llm_base_url or "")

    if new_base:
        try:
            validate_llm_base_url(new_base)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"LLM 接口地址无效：{exc}") from exc
        if base_changed and not new_key:
            raise HTTPException(status_code=422, detail="更换 LLM 接口地址时必须同时填写新的 LLM API Key（不能沿用旧 Key）")
    elif base_changed and not new_key:
        raise HTTPException(status_code=422, detail="修改 LLM 接口地址时必须同时填写新的 LLM API Key（不能沿用旧 Key）")

    if new_key:
        config.llm_api_key = encrypt_secret(new_key)
    config.llm_base_url = new_base or None
    config.llm_model = payload.llm_model.strip() if payload.llm_model and payload.llm_model.strip() else None
    config.updated_by = user.email
    write_operation_log(db, user, "update_llm_config", "gateway_api_config", "1", {"model": config.llm_model})
    db.commit()
    db.refresh(config)
    return serialize_gateway_config(config)


# ══════════════════════════════════════════════════════════════════
# 3.17.3 独立测试搜索接口
# ══════════════════════════════════════════════════════════════════
@router.post("/api/admin/api-gateway/test-search")
async def test_search_gateway(payload: SearchTestRequest, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> dict:
    if payload.search_provider not in SUPPORTED_SEARCH_PROVIDERS:
        raise HTTPException(status_code=422, detail="不支持的搜索服务商")
    saved = get_gateway_config(db)
    provider = payload.search_provider or saved.search_provider

    form_key = payload.search_api_key.strip()
    provider_changed = provider != saved.search_provider
    if provider == "custom":
        if not form_key:
            return {"ok": False, "error": "自定义服务商必须填写新的搜索 API Key（不能沿用旧 Key）"}
        api_key = form_key
    else:
        if provider_changed and not form_key:
            return {"ok": False, "error": "切换搜索服务商时必须填写新的搜索 API Key（不能沿用旧 Key）"}
        api_key = form_key or decrypt_secret(saved.search_api_key) or ""
    if not api_key:
        return {"ok": False, "error": "请先填写搜索 API Key（输入框留空时会使用已保存的 Key，当前两者都为空）"}

    if provider == "custom":
        base_url = (payload.search_base_url or "").strip()
        if not base_url:
            return {"ok": False, "error": "自定义服务商需要填写 https:// 接口地址"}
        try:
            base_url = validate_gateway_url(base_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"接口地址无效：{exc}") from exc
    else:
        base_url = DEFAULT_SEARCH_BASE_URLS.get(provider, "")

    test_config = SearchGatewayConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=max(3, payload.search_timeout_seconds),
        max_results=max(1, payload.search_max_results),
        model=(payload.search_model or "").strip() or (saved.search_model or "").strip() or None,
    )
    started = time.perf_counter()
    try:
        if provider == "deepseek":
            reply, sources = await ping_deepseek_search(test_config, payload.query)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if not reply:
                return {"ok": False, "error": "DeepSeek 联网检索未返回内容"}
            return {
                "ok": True,
                "query": payload.query,
                "result_count": len(sources),
                "elapsed_ms": elapsed_ms,
                "first_results": [item.get("title") for item in sources[:3]],
                "reply": reply[:200],
            }
        results = await search_single_query(test_config, payload.query)
    except Exception as exc:
        return {"ok": False, "error": f"调用失败：{exc}"}
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "ok": True,
        "query": payload.query,
        "result_count": len(results),
        "elapsed_ms": elapsed_ms,
        "first_results": [item.get("title") for item in results[:3]],
    }


# ══════════════════════════════════════════════════════════════════
# 3.17.4 独立测试大模型接口
# ══════════════════════════════════════════════════════════════════
@router.post("/api/admin/api-gateway/test-llm")
async def test_llm_gateway(payload: LlmTestRequest, db: Session = Depends(get_db), user: User = Depends(AdminOnly)) -> dict:
    saved = get_gateway_config(db)
    settings = get_settings()

    form_key = payload.llm_api_key.strip()
    form_base = payload.llm_base_url.strip() if payload.llm_base_url else ""
    base_changed = form_base and form_base != (saved.llm_base_url or "")
    if form_base and base_changed and not form_key:
        return {"ok": False, "error": "更换 LLM 接口地址时必须同时填写新的 LLM API Key（不能沿用旧 Key）"}
    if form_base:
        try:
            form_base = validate_llm_base_url(form_base)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"LLM 接口地址无效：{exc}") from exc

    saved_base = (saved.llm_base_url or "").strip()
    saved_key = decrypt_secret(saved.llm_api_key)
    if form_key:
        api_key = form_key
    else:
        api_key = saved_key or settings.deepseek_api_key or ""
        # 网关保存了自定义 LLM 地址但网关 Key 不可用（如加密密钥轮换）：
        # 禁止把 .env 的 DeepSeek Key 发往该地址。
        if saved_base and not saved_key:
            return {"ok": False, "error": "已保存的 LLM 接口地址存在，但网关 Key 无法解密（加密密钥可能已轮换），请重新填写 LLM API Key 并保存"}
    if not api_key:
        return {"ok": False, "error": "未找到可用的 LLM API Key（表单留空时依次使用已保存配置与 .env，当前均为空）"}

    base_url = form_base or saved_base or settings.deepseek_base_url
    model = (payload.llm_model or "").strip() or (saved.llm_model or "").strip() or settings.deepseek_model

    started = time.perf_counter()
    try:
        reply = await ping_llm(api_key, base_url, model, settings.deepseek_timeout_seconds)
    except Exception as exc:
        return {"ok": False, "error": f"调用失败：{exc}"}
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {"ok": True, "model": model, "elapsed_ms": elapsed_ms, "reply": reply[:200]}

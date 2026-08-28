"""结构化报告渲染测试 — AI 输出的 6 部分 JSON 渲染为 HTML。"""

import json

from app.service.report_content import build_report_presentation_html
from app.service.reporting import parse_structured_report, render_structured_report_html


def _payload() -> dict:
    return {
        "company": {"name": "奥飞娱乐", "industry": "制造业", "size": "1-200人", "position": "IT", "ai_focus": "想提升获客、销售转化和客户跟进效率", "public_info": "公司介绍：奥飞娱乐；营收：2023 年 27.39 亿元。"},
        "score": {"total": 120, "max_score": 260, "score_rate": 0.4615},
        "dimensions": [
            {"module_code": "M01", "module_name": "一心", "raw_score": 12, "max_score": 28, "score_rate": 0.4285},
            {"module_code": "M02", "module_name": "简化业务", "raw_score": 18, "max_score": 28, "score_rate": 0.6428},
        ],
        "low_dimensions": [
            {"module_code": "M01", "module_name": "一心", "raw_score": 12, "max_score": 28, "score_rate": 0.4285}
        ],
        "cases": [],
    }


def _report_data() -> dict:
    return {
        "executive_summary": [
            {"finding": "战略清晰度是全卷最低点", "evidence": "Q5 仅 3.69 分，4-5 分占比 44.4%。"}
        ],
        "dimension_analysis": [
            {
                "module_code": "M01",
                "module_name": "一心",
                "core_conclusion": "该维度得分率42.86%，呈现“理念强、机制弱”的特征。",
                "evidence_rows": [
                    {"evidence": "Q4“用户满意度在绩效考核中的权重”得分4/4（100%）", "interpretation": "说明公司上下有较强的用户导向意识；"},
                    {"evidence": "但Q1“系统性的用户研究与洞察机制”仅1/4（25%）", "interpretation": "说明用户声音获取和传导依赖个案或经验，缺乏机制化闭环。"},
                ],
            },
            {"module_code": "M02", "module_name": "简化业务", "analysis": "简化业务维度得分率 64.3%，业务聚焦有一定基础。"},
        ],
        "key_contradictions": [
            {"contradiction": "局部清晰 vs. 整体模糊", "evidence": "用户画像 4.75 分 vs 年度目标 3.69 分", "diagnosis": "洞察未转化为取舍。"}
        ],
        "workshop_topics": [
            {"priority": "P0", "topic": "选择唯一主战役", "question": "哪个方向最值得集中资源？", "deliverable": "主战役陈述；胜利指标", "nature": "必须形成选择"}
        ],
        "ai_scenarios": [
            {"name": "销售线索评分助手", "direction": "销售运营 · 闪电战", "description": "根据行业、规模、预算自动给线索打标签。", "benefit": "提升高意向客户识别效率。"}
        ],
        "management_actions": ["两周内完成事实核验", "30 天内确定一个优先试点", "建立月度复盘机制"],
    }


def test_parse_structured_report_handles_markdown_fence():
    text = '```json\n{"executive_summary": [{"finding": "a", "evidence": "b"}]}\n```'
    data = parse_structured_report(text)
    assert data and data["executive_summary"][0]["finding"] == "a"


def test_parse_structured_report_returns_none_on_garbage():
    assert parse_structured_report("抱歉，我无法生成报告") is None
    assert parse_structured_report("") is None


def test_structured_report_renders_all_six_sections():
    html = render_structured_report_html(_payload(), _report_data())
    assert "一、执行摘要" in html
    assert "二、能力成熟度分析" in html
    assert "三、关键矛盾与核心诊断" in html
    assert "四、工作坊议题地图" in html
    assert "五、优先 AI 场景与案例" in html
    assert "六、管理层行动建议" in html
    # 表格与内容
    assert "战略清晰度是全卷最低点" in html
    assert "局部清晰 vs. 整体模糊" in html
    assert "选择唯一主战役" in html
    assert "销售线索评分助手" in html
    assert "适用方向" not in html
    assert "闪电战" not in html
    assert "两周内完成事实核验" in html
    # 维度分析按模块对齐（三栏表格形式）
    assert "M01 一心" in html
    assert "42.86%" in html
    assert "12/28" in html
    # 三栏表格：核心结论 | 数据依据 | 分析解读
    assert "核心结论" in html
    assert "数据依据" in html
    assert "分析解读" in html
    assert "该维度得分率42.86%，呈现“理念强、机制弱”的特征。" in html
    assert "说明用户声音获取和传导依赖个案或经验，缺乏机制化闭环。" in html
    # 旧格式回退：仅 analysis 文本的模块仍渲染为段落
    assert "简化业务维度得分率 64.3%" in html
    # XSS 转义
    assert "<script>" not in html


def test_structured_report_escapes_user_input():
    payload = _payload()
    data = _report_data()
    data["executive_summary"] = [{"finding": '<script>alert(1)</script>', "evidence": "x"}]
    html = render_structured_report_html(payload, data)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_v2_presentation_is_five_sections_and_derives_layout_without_mutating_body():
    payload = _payload()
    payload.update({
        "report_format_version": 2,
        "report_contact": {
            "contact_name": "历史联系人",
            "phone": "10086",
            "wechat": "historical-wechat",
            "email": "historical@example.com",
        },
    })
    stored_html = render_structured_report_html(payload, _report_data())
    stored_copy = stored_html
    presentation = build_report_presentation_html(
        stored_html,
        json.dumps(payload, ensure_ascii=False),
    )

    assert stored_html == stored_copy
    assert "report-module-judgment" not in stored_html
    assert "report-module-judgment" in presentation
    assert "用户价值导向正处于能力建设阶段" in presentation
    assert "以下场景仅供决策参考，具体需入企调研后给出更详细的建议。" in presentation
    assert "1. 销售线索评分助手" in presentation
    assert "六、管理层行动建议" not in presentation
    assert "管理层" not in presentation
    assert "进一步沟通" not in presentation
    assert "历史联系人" in presentation
    assert "historical@example.com" in presentation
    assert "report-contact-callout" in presentation


# ══════════════════════════════════════════════════════════════════
# call_deepseek：网关 Key 失效时不得把 .env DeepSeek Key 发往自定义地址
# ══════════════════════════════════════════════════════════════════
import asyncio
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.service import reporting
from app.service.api_gateway_service import LlmGatewayOverride
from app.service.reporting import call_deepseek


class _FakeHttpClient:
    requests: list[tuple[str, dict]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        return None

    async def post(self, url, headers=None, json=None):
        type(self).requests.append((url, headers or {}))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": "生成内容"}}]},
        )


def _env_settings(monkeypatch, **kwargs) -> None:
    monkeypatch.setattr(
        reporting,
        "get_settings",
        lambda: Settings(deepseek_api_key="sk-env", deepseek_base_url="https://api.deepseek.com", _env_file=None, **kwargs),
    )


def test_call_deepseek_refuses_env_key_with_custom_base(monkeypatch):
    """网关保存了自定义 LLM 地址但网关 Key 不可用（解密失败）时，
    禁止把 .env 的 DeepSeek Key 发往该地址，直接失败提示管理员。"""
    _env_settings(monkeypatch)
    _FakeHttpClient.requests.clear()
    monkeypatch.setattr(reporting.httpx, "AsyncClient", _FakeHttpClient)

    override = LlmGatewayOverride(api_key=None, base_url="https://third-party-llm.example", model=None)
    with pytest.raises(RuntimeError, match="无法解密"):
        asyncio.run(call_deepseek({}, llm_override=override))

    assert _FakeHttpClient.requests == []


def test_call_deepseek_env_fallback_uses_official_endpoint(monkeypatch):
    """未配置网关地址时，正常回退 .env Key + 官方地址。"""
    _env_settings(monkeypatch)
    _FakeHttpClient.requests.clear()
    monkeypatch.setattr(reporting.httpx, "AsyncClient", _FakeHttpClient)

    result = asyncio.run(call_deepseek({}, llm_override=LlmGatewayOverride(api_key=None, base_url=None, model=None)))

    assert result == "生成内容"
    url, headers = _FakeHttpClient.requests[0]
    assert url == "https://api.deepseek.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-env"


def test_call_deepseek_uses_gateway_key_with_custom_base(monkeypatch):
    """网关地址与网关 Key 均可用时，使用网关 Key 调用自定义地址（合法配置不受影响）。"""
    _env_settings(monkeypatch)
    _FakeHttpClient.requests.clear()
    monkeypatch.setattr(reporting.httpx, "AsyncClient", _FakeHttpClient)

    override = LlmGatewayOverride(api_key="sk-gateway", base_url="https://third-party-llm.example", model=None)
    result = asyncio.run(call_deepseek({}, llm_override=override))

    assert result == "生成内容"
    url, headers = _FakeHttpClient.requests[0]
    assert url == "https://third-party-llm.example/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-gateway"


def test_generate_report_candidate_validates_before_mutating_report(monkeypatch):
    report = SimpleNamespace(
        submission=SimpleNamespace(lead=SimpleNamespace(), dimension_scores=[]),
        company_research_json='{"evidence_version": 1}',
        html_content="old html",
        summary_json='{"old": true}',
        status="generated",
    )
    monkeypatch.setattr(reporting, "select_recommendations", lambda *_args: [])
    monkeypatch.setattr(reporting, "build_report_payload", lambda *_args, **_kwargs: {
        "report_format_version": 2,
        "dimensions": [],
    })
    monkeypatch.setattr(reporting, "report_contact_snapshot", lambda _db: {})
    monkeypatch.setattr(reporting, "effective_llm_override", lambda _db: None)

    async def invalid_model(*_args, **_kwargs):
        return '{"executive_summary": []}'

    monkeypatch.setattr(reporting, "call_deepseek", invalid_model)
    with pytest.raises(reporting.ReportContentInvalidError):
        asyncio.run(reporting.generate_report_candidate(object(), report))

    assert report.html_content == "old html"
    assert report.summary_json == '{"old": true}'
    assert report.status == "generated"

"""结构化报告渲染测试 — AI 输出的 6 部分 JSON 渲染为 HTML。"""

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
            {"module_code": "M01", "module_name": "一心", "analysis": "一心维度得分率 42.9%，用户洞察相关题目偏低，建议优先补齐。"},
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
    assert "两周内完成事实核验" in html
    # 维度分析按模块对齐（表格形式）
    assert "M01 一心" in html
    assert "42.9%" in html
    assert "12/28" in html
    # XSS 转义
    assert "<script>" not in html


def test_structured_report_escapes_user_input():
    payload = _payload()
    data = _report_data()
    data["executive_summary"] = [{"finding": '<script>alert(1)</script>', "evidence": "x"}]
    html = render_structured_report_html(payload, data)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html

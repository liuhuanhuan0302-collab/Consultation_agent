from app.service.reporting import render_fallback_html


def test_fallback_report_does_not_invent_unknown_company_facts():
    payload = {
        "company": {"name": "测试公司", "industry": "制造业", "size": "200-1000人", "position": "CEO", "ai_focus": ""},
        "score": {"total": 120, "max_score": 260, "score_rate": 0.4615, "risk_level": "较弱"},
        "dimensions": [
            {"module_code": "M01", "module_name": "一心", "raw_score": 12, "max_score": 28, "score_rate": 0.4285, "risk_level": "较弱"}
        ],
        "low_dimensions": [
            {"module_code": "M01", "module_name": "一心", "raw_score": 12, "max_score": 28, "score_rate": 0.4285}
        ],
        "cases": [
            {
                "title": "智能客服知识库",
                "industry": "通用",
                "function_area": "客户服务",
                "priority_tag": "闪电战",
                "description": "用企业 FAQ 搭建客服助手。",
                "expected_benefit": "提升响应速度。",
            }
        ],
    }

    html = render_fallback_html(payload)

    assert "测试公司" in html
    assert "120/260" in html
    assert "智能客服知识库" in html
    assert "融资" not in html

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


def test_fallback_report_renders_template_style_findings_from_dynamic_question_data():
    payload = {
        "company": {"name": "测试公司", "industry": "制造业", "size": "200-1000人", "position": "CEO", "ai_focus": "流程自动化"},
        "score": {"total": 120, "max_score": 260, "score_rate": 0.4615},
        "dimensions": [
            {"module_code": "M01", "module_name": "一心", "raw_score": 12, "max_score": 28, "score_rate": 0.4285},
            {"module_code": "M02", "module_name": "简化业务", "raw_score": 18, "max_score": 28, "score_rate": 0.6428},
        ],
        "low_dimensions": [
            {"module_code": "M01", "module_name": "一心", "raw_score": 12, "max_score": 28, "score_rate": 0.4285}
        ],
        "question_scores": [
            {"question_code": "M01-Q01", "question_text": "是否明确客户价值？", "module_code": "M01", "module_name": "一心", "score": 1, "max_score": 4, "score_rate": 0.25},
            {"question_code": "M02-Q01", "question_text": "是否有业务优先级？", "module_code": "M02", "module_name": "简化业务", "score": 3, "max_score": 4, "score_rate": 0.75},
        ],
        "core_findings": [
            {"finding": "一心是当前最需要优先补齐的环节", "evidence": "M01-Q01 得分 1/4", "meaning": "应先核验客户价值与负责人。"}
        ],
        "cases": [],
    }

    html = render_fallback_html(payload)

    assert "核心发现与证据" in html
    assert "M01-Q01" in html
    assert "题项得分排序" not in html
    assert "整体诊断画像" not in html

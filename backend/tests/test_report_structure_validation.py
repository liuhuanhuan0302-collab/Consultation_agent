from app.service.reporting import report_data_validation_errors


def payload():
    return {
        "dimensions": [
            {"module_code": "M01"},
            {"module_code": "M02"},
        ]
    }


def complete_report():
    return {
        "executive_summary": [{"finding": "发现", "evidence": "证据"}],
        "dimension_analysis": [
            {"module_code": "M01", "core_conclusion": "结论"},
            {"module_code": "M02", "core_conclusion": "结论"},
        ],
        "key_contradictions": [{"contradiction": "矛盾"}],
        "workshop_topics": [{"topic": "议题"}],
        "ai_scenarios": [{"name": "场景"}],
        "management_actions": ["行动"],
    }


def test_complete_report_passes_without_strict_item_counts():
    assert report_data_validation_errors(complete_report(), payload()) == []


def test_every_report_section_must_exist():
    report = complete_report()
    report["ai_scenarios"] = []

    errors = report_data_validation_errors(report, payload())

    assert "缺少或未填写：优先 AI 应用场景" in errors


def test_dimension_analysis_must_cover_every_active_module():
    report = complete_report()
    report["dimension_analysis"] = report["dimension_analysis"][:1]

    errors = report_data_validation_errors(report, payload())

    assert "逐维分析未覆盖模块：M02" in errors

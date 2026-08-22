from app.service.report_content import sanitize_report_content


def test_sanitize_report_content_removes_legacy_scenario_direction() -> None:
    source = """
    <section class="report-case">
      <h4>智能线索评分</h4>
      <p><strong>适用方向：</strong>获客·攻坚战</p>
      <p>根据客户数据评估线索质量。</p>
      <p><strong>预期收益：</strong>提升跟进效率。</p>
    </section>
    """

    result = sanitize_report_content(source)

    assert "适用方向" not in result
    assert "攻坚战" not in result
    assert "智能线索评分" in result
    assert "根据客户数据评估线索质量" in result
    assert "提升跟进效率" in result


def test_sanitize_report_content_removes_tactic_terms_outside_direction_line() -> None:
    result = sanitize_report_content("<p>不应再给出闪电战、升维战等判断。</p>")

    assert "闪电战" not in result
    assert "升维战" not in result
    assert "不应再给出" in result

from app.api.v1.endpoints.admin.leads import lead_word_filename


def test_lead_word_filename_uses_company_name() -> None:
    assert lead_word_filename("奥飞娱乐") == "奥飞娱乐客户详情.docx"


def test_lead_word_filename_removes_windows_invalid_characters() -> None:
    assert lead_word_filename("奥飞/娱乐:*?") == "奥飞娱乐客户详情.docx"


def test_lead_word_filename_has_fallback_for_missing_company_name() -> None:
    assert lead_word_filename(None) == "客户客户详情.docx"

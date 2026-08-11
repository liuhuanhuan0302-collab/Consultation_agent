import pytest

from app.api.v1.endpoints.admin import escape_csv_cell


@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1:A2)", "-10+10", "@SUM(A1:A2)", "  =1+1", "\t@SUM(A1:A2)"])
def test_escape_csv_formula_prefixes(value):
    assert escape_csv_cell(value) == f"'{value}"


@pytest.mark.parametrize("value", ["普通企业名称", "2026-07-29", "", None, 42])
def test_keep_safe_csv_values_unchanged(value):
    assert escape_csv_cell(value) == value

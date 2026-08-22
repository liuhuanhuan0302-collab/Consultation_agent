"""最终报告内容的兼容清洗规则。"""

from __future__ import annotations

import re


_SCENARIO_DIRECTION_PARAGRAPH_RE = re.compile(
    r"<p\b[^>]*>\s*(?:<strong\b[^>]*>\s*)?适用方向\s*[：:]?[\s\S]*?</p>",
    flags=re.IGNORECASE,
)
_TACTIC_JUDGEMENT_RE = re.compile(r"(?:攻坚战|闪电战|升维战)")


def sanitize_report_content(value: str | None) -> str:
    """隐藏不可靠的场景战法判断，并兼容已经生成的历史报告。"""
    if not value:
        return ""
    cleaned = _SCENARIO_DIRECTION_PARAGRAPH_RE.sub("", value)
    return _TACTIC_JUDGEMENT_RE.sub("", cleaned)

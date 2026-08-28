"""最终报告正文的兼容清洗与统一展示规则。"""

from __future__ import annotations

import re
import json
from html import escape, unescape


_SCENARIO_DIRECTION_PARAGRAPH_RE = re.compile(
    r"<p\b[^>]*>\s*(?:<strong\b[^>]*>\s*)?适用方向\s*[：:]?[\s\S]*?</p>",
    flags=re.IGNORECASE,
)
_TACTIC_JUDGEMENT_RE = re.compile(r"(?:攻坚战|闪电战|升维战)")
_MANAGEMENT_SECTION_RE = re.compile(
    r"<section\b[^>]*>\s*<h2\b[^>]*>\s*六[、.]\s*管理层[\s\S]*?</section>",
    flags=re.IGNORECASE,
)
_MANAGEMENT_TRAILING_RE = re.compile(
    r"<h2\b[^>]*>\s*六[、.]\s*管理层[\s\S]*?</h2>[\s\S]*?"
    r"(?=<h2\b|<section\b[^>]*report-contact-section|</article>|$)",
    flags=re.IGNORECASE,
)
_CONTACT_SECTION_RE = re.compile(
    r"<section\b[^>]*class=(?:\"[^\"]*report-contact-section[^\"]*\"|'[^']*report-contact-section[^']*')[^>]*>[\s\S]*?</section>",
    flags=re.IGNORECASE,
)
_MODULE_HEAD_RE = re.compile(
    r"(<div\b[^>]*class=(?:\"[^\"]*report-module-head[^\"]*\"|'[^']*report-module-head[^']*')[^>]*>[\s\S]*?</div>)",
    flags=re.IGNORECASE,
)
_SCENARIO_NOTE_RE = re.compile(
    r"<p\b[^>]*class=(?:\"[^\"]*report-section-note[^\"]*\"|'[^']*report-section-note[^']*')[^>]*>\s*以下场景[\s\S]*?</p>",
    flags=re.IGNORECASE,
)
_SCENARIO_SECTION_NOTE_RE = re.compile(
    r"(<h2\b[^>]*>\s*五[、.]\s*优先\s*AI\s*场景[^<]*</h2>\s*)"
    r"<p\b[^>]*class=(?:\"[^\"]*report-section-note[^\"]*\"|'[^']*report-section-note[^']*')[^>]*>[\s\S]*?</p>",
    flags=re.IGNORECASE,
)
_SCENARIO_HEADING_RE = re.compile(
    r"(<section\b[^>]*class=(?:\"[^\"]*report-case[^\"]*\"|'[^']*report-case[^']*')[^>]*>\s*<h4\b[^>]*>)([\s\S]*?)(</h4>)",
    flags=re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


MODULE_JUDGMENT_RULES: dict[str, tuple[str, str, str]] = {
    "M01": (
        "本模块表现相对稳健，用户价值导向已具备良好基础。",
        "用户价值导向已有初步基础，进一步完善洞察与反馈闭环将释放更大协同空间。",
        "用户价值导向正处于能力建设阶段，优先建立稳定的洞察与反馈闭环将更易形成成效。",
    ),
    "M02": (
        "业务简化表现相对稳健，关键业务聚焦已具备良好基础。",
        "业务简化已有初步基础，进一步聚焦关键流程将释放更大协同空间。",
        "业务简化正处于能力建设阶段，优先聚焦关键流程将更易形成成效。",
    ),
    "M03": (
        "组织简练表现相对稳健，权责与协作机制已具备良好基础。",
        "组织简练具备一定基础，权责与协作机制仍有持续优化空间。",
        "组织简练正处于能力建设阶段，优先厘清权责与协作机制将更易形成成效。",
    ),
    "M04": (
        "团队协同表现相对稳健，统一目标与跨团队联动已具备良好基础。",
        "团队协同已有实践积累，统一目标与跨团队联动可进一步加强。",
        "团队协同正处于能力建设阶段，优先统一目标与协作节奏将更易形成成效。",
    ),
    "M05": (
        "流程化建设表现相对稳健，关键流程标准化已具备良好基础。",
        "流程化建设已形成一定基础，关键流程标准化仍有提升空间。",
        "流程化建设正处于能力建设阶段，优先固化高频关键流程将更易形成成效。",
    ),
    "M06": (
        "自动化应用表现相对稳健，高频流程提效已具备良好基础。",
        "自动化应用已有初步基础，进一步覆盖高频流程将释放更大协同空间。",
        "自动化应用正处于能力建设阶段，优先夯实高频流程将更易形成成效。",
    ),
    "M07": (
        "数字化基础表现相对稳健，核心数据贯通已具备良好基础。",
        "数字化基础已有初步积累，进一步贯通核心数据将释放更大协同空间。",
        "数字化基础正在逐步完善，核心数据贯通将成为下一阶段重点。",
    ),
    "M08": (
        "智能化应用已有较好基础，继续强化场景闭环有望放大业务价值。",
        "智能化应用已有初步基础，进一步强化场景闭环将释放更大业务价值。",
        "智能化应用正处于能力建设阶段，优先验证高价值场景闭环将更易形成成效。",
    ),
    "M09": (
        "生态协同表现相对稳健，平台化能力具备进一步延展空间。",
        "生态协同已有初步基础，进一步强化平台化连接将释放更大协同空间。",
        "生态协同正处于能力建设阶段，优先建立稳定连接机制将更易形成成效。",
    ),
}


def sanitize_report_content(value: str | None) -> str:
    """隐藏不可靠的场景战法判断，并兼容已经生成的历史报告。"""
    if not value:
        return ""
    cleaned = _SCENARIO_DIRECTION_PARAGRAPH_RE.sub("", value)
    return _TACTIC_JUDGEMENT_RE.sub("", cleaned)


def module_judgment(module_code: str, score_rate: float) -> str:
    """Return a restrained deterministic renderer note for one maturity module."""

    rules = MODULE_JUDGMENT_RULES.get(str(module_code or "").strip().upper())
    if not rules:
        return ""
    try:
        rate = float(score_rate)
    except (TypeError, ValueError):
        rate = 0.0
    return rules[0] if rate >= 0.7 else rules[1] if rate >= 0.45 else rules[2]


def _summary_payload(summary_json: str | None) -> dict:
    try:
        value = json.loads(summary_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _plain_html(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub("", value))).strip()


def _historical_contact(section_html: str) -> dict[str, str]:
    contact: dict[str, str] = {}
    for key, label in (
        ("contact_name", "联系人"),
        ("phone", "电话"),
        ("wechat", "微信号"),
        ("email", "邮箱"),
    ):
        match = re.search(
            rf"{label}\s*[：:]\s*</strong>\s*([^<]+)",
            section_html,
            flags=re.IGNORECASE,
        )
        if match and (value := _plain_html(match.group(1))):
            contact[key] = value
    return contact


def _contact_callout(contact: dict) -> str:
    values = {
        key: str(contact.get(key) or "").strip()
        for key in ("contact_name", "phone", "wechat", "email")
    }
    details = " | ".join(
        f"{label}：{escape(values[key])}"
        for key, label in (
            ("contact_name", "联系人"),
            ("phone", "电话"),
            ("wechat", "微信号"),
            ("email", "邮箱"),
        )
        if values[key]
    )
    if not details:
        return ""
    return (
        '<div class="report-diagnosis-callout report-contact-callout">'
        "<p>如需入企调研或进一步了解，可以联系：</p>"
        f"<p>{details}</p>"
        "</div>"
    )


def build_report_presentation_html(html_content: str | None, summary_json: str | None) -> str:
    """Build the shared, non-persistent customer-report body presentation.

    Historical snapshots keep their AI prose and scores. Layout-only additions
    (module judgments, approved scene copy and contact callout) are derived here
    for public/admin HTML and both Word exports without mutating ``Report.html_content``.
    """

    rendered = sanitize_report_content(html_content)
    if not rendered:
        return ""
    summary = _summary_payload(summary_json)
    dimensions = {
        str(item.get("module_code") or "").strip().upper(): item
        for item in (summary.get("dimensions") or [])
        if isinstance(item, dict)
    }

    rendered = _MANAGEMENT_SECTION_RE.sub("", rendered)
    rendered = _MANAGEMENT_TRAILING_RE.sub("", rendered)
    contact_match = _CONTACT_SECTION_RE.search(rendered)
    historical_contact = _historical_contact(contact_match.group(0)) if contact_match else {}
    rendered = _CONTACT_SECTION_RE.sub("", rendered)

    def add_judgment(match: re.Match[str]) -> str:
        head = match.group(1)
        plain = _plain_html(head)
        code_match = re.search(r"\b(M\d{2})\b", plain, flags=re.IGNORECASE)
        if not code_match:
            return head
        code = code_match.group(1).upper()
        dimension = dimensions.get(code) or {}
        judgment = module_judgment(code, dimension.get("score_rate", 0))
        if not judgment:
            return head
        return head + f'<p class="report-module-judgment">{escape(judgment)}</p>'

    rendered = _MODULE_HEAD_RE.sub(add_judgment, rendered)
    approved_scene_note = (
        '<p class="report-section-note report-section-note--accent">'
        "以下场景仅供决策参考，具体需入企调研后给出更详细的建议。"
        "</p>"
    )
    rendered = _SCENARIO_SECTION_NOTE_RE.sub(
        lambda match: match.group(1) + approved_scene_note,
        rendered,
    )
    rendered = _SCENARIO_NOTE_RE.sub(
        approved_scene_note,
        rendered,
    )
    scenario_number = 0

    def number_scenario(match: re.Match[str]) -> str:
        nonlocal scenario_number
        scenario_number += 1
        title = re.sub(r"^\s*\d+\s*[.、]\s*", "", _plain_html(match.group(2)))
        return f"{match.group(1)}{scenario_number}. {escape(title)}{match.group(3)}"

    rendered = _SCENARIO_HEADING_RE.sub(number_scenario, rendered)
    contact = summary.get("report_contact")
    if not isinstance(contact, dict) or not any(str(value or "").strip() for value in contact.values()):
        contact = historical_contact
    callout = _contact_callout(contact)
    if callout:
        closing = re.search(r"</article>\s*$", rendered, flags=re.IGNORECASE)
        if closing:
            rendered = rendered[: closing.start()] + callout + rendered[closing.start() :]
        else:
            rendered += callout
    return rendered

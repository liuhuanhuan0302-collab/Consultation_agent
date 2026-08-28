# I-090: Report advisory wording and global contact settings

Status: Accepted  
Owner: delegated_report_settings_worker  
Turn: TURN-0015 (completed)

## Objective

For newly generated or explicitly regenerated reports, rename section five to
"五、优先 AI 场景建议", add the fixed cautious disclaimer containing the
customer company name, remove management action advice completely, and append
an unnumbered "进一步沟通" contact block sourced from administrator-managed
global settings. Preserve existing report snapshots.

## Requirements

- Add a layered singleton settings domain (API -> service -> repository -> model)
  for contact name, phone, WeChat, and email, with an Alembic migration.
- Only the `admin` role may read or update this settings API. Add an admin-only
  left-navigation "系统设置" screen; do not expose editing to other roles.
- Empty individual contact fields are omitted; when all four fields are empty,
  omit the entire contact block and do not fail report generation.
- Capture the settings into each new/regenerated report's persisted summary
  snapshot. Rendering and export must use this snapshot, never current live
  settings, so later setting changes cannot mutate an existing report.
- Add a report-format version or equivalent compatibility rule: old reports and
  exports remain unchanged, while new reports omit management actions.
- Remove management actions from the new AI prompt, required structured-output
  validation, and all new HTML/Word/PDF rendering paths.
- Keep dynamic evidence-backed AI scene suggestions and each scene's expected
  benefit. Do not require a rigid scene count when evidence is insufficient.
- The exact section-five disclaimer is:
  `以下场景基于本次诊断结果与【客户公司名称】的公开信息生成，仅供决策参考（具体需入企调研后给出更详细的建议）。`
- HTML/web, Word, converted PDF, and email attachment content must derive from
  the same persisted report snapshot.
- Add focused tests for authorization, partial/all-empty settings, snapshot
  immutability, new/legacy report compatibility, exact wording, and Word output.
- Run the focused tests, full backend suite, frontend build, Alembic single-head
  check, and `git diff --check`.
- Do not stage, commit, deploy, access production data, or send real email.

## Non-goals

No QR code, address, multiple contacts, report scoring changes, company-search
changes, queue/retry changes, SMTP changes, or official website changes.

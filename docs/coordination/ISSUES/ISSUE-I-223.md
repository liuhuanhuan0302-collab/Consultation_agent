# I-223: Remove organization diagnosis filter bars

Status: Accepted
Ownership: leased frontend paths only

## Objective

Remove both organization-diagnosis filter bars and make the remaining list
behavior explicit and deterministic.

## Scope and acceptance

- Company list: retain the `组织诊断` title and `刷新` action; remove the entire
  company-name/date/sample/query/count filter row.
- Company list data is fixed to companies with at least one submitted answer.
- Company answer list: remove the entire department/status/name/date/query row.
- Company answer list is fixed to submitted answers only.
- Rename `导出当前筛选` to `导出已提交答卷` and export submitted answers only.
- Preserve pagination, refresh, company open/back, answer open/back, report
  actions, backend filter capability and all historical data.
- Remove styles/render state used only by the deleted controls where safe.
- `npm run build` passes; desktop/mobile browser checks show no overflow and
  the fixed submitted-only behavior.
- No backend, migration, schema, database, lead-PDF, commit or deployment work.

# ISSUE I-180: Add persistent three-tier report queue domain

## Objective

Create the database-backed queue-state and dynamic-setting foundation for a
three-tier report scheduler, with atomic placement, promotion and explicit
manual approval semantics.

## Human-approved contract

- Defaults: processing concurrency 2, active capacity 50, automatic waiting
  capacity 200, PDF concurrency 1, processing/promotion not paused.
- Queue states: `active`, `automatic_waiting`, `manual_review`,
  `approved_waiting`; terminal jobs have no queue state.
- Lifecycle states remain `queued`, `processing`, `sent`, `failed`, and add
  `cancelled`.
- New jobs fill active, then automatic waiting, then manual review. Before a new
  job is placed, already approved waiting jobs receive priority for any first-
  or second-tier capacity.
- Manual-review jobs never auto-release merely because settings increase; they
  require single/batch approval. Approved jobs still respect capacities.
- Settings-row locking is the serialization boundary for placement/promotion.
- Capacity reductions do not evict or move existing tasks.

## Scope

- ORM enums/models and compatibility exports.
- New Alembic migration from the current single head; no runtime DDL.
- Queue settings and queue-placement repositories.
- Small queue-scheduling service for locked settings retrieval, placement,
  promotion, approval/rejection and validation.
- Focused tests including default 251-job tier distribution, approved priority,
  no auto-release of manual review, validation and migration chain/head.

## Non-goals

- Do not yet connect the new scheduler to public/admin HTTP or the worker loop.
- No frontend/API schemas, live queue processing, production data, deployment,
  stage, commit, push, external calls or real email.

## Acceptance conditions

1. Migration creates the settings table and all task columns/indexes with safe
   backfill for existing nonterminal jobs.
2. Exactly one Alembic head remains.
3. Defaults and validation enforce active capacity >= processing concurrency and
   PDF concurrency <= processing concurrency.
4. Sequential placement of 251 new tasks yields 50 active, 200 automatic and 1
   manual-review task under defaults.
5. Manual-review tasks do not auto-promote; approved tasks are prioritized and
   never exceed configured capacities.
6. All focused tests and the complete backend suite pass.

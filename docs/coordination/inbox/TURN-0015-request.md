# TURN-0015 repair request

Repair only the three findings in REV-I-090-1:

1. Update the migration-chain test's expected head to `3e7d1b9c5a20`.
2. Replace compatibility imports in the new system-settings endpoint and its new
   focused test with canonical layered imports where applicable.
3. In `loadAdminTab`, reject or redirect `settings` when the current role is not
   admin, so hidden navigation is not the only frontend control. Keep API auth as
   the authoritative security boundary.

Run the focused tests, full backend suite, frontend build, `alembic heads`, and
`git diff --check`. Append the development record and create the handoff. Do not
change any other behavior or file.

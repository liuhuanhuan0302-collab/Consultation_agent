# Claude Code repository entrypoint

Before taking any action, read and follow these files in order:

1. `AGENTS.md`
2. `backend/ARCHITECTURE.md`
3. `docs/coordination/PROTOCOL.md`
4. `docs/coordination/STATE.json`
5. The active issue named by `STATE.json`
6. `docs/coordination/OWNERSHIP.yaml`

`AGENTS.md` is the authoritative shared rule set. This file does not create a
second policy. If no active issue is assigned to Claude Code, or the ownership
lease does not list Claude Code as the current writer, do not modify files.

For the automated repair loop, append development evidence only to
`docs/coordination/DEVELOPMENT_LOG.md`; never edit `REVIEW_LOG.md`. A task is
ready for Codex only after a complete `READY_FOR_REVIEW` entry. Read the latest
review entry before starting a repair. Do not start a fourth repair attempt or
continue after a `BLOCKED` entry; request human intervention instead.

Do not commit, stage, deploy, delete unrelated files, access production data, or
send real email. Return the required development-log entry and exit after the
assigned issue is complete.

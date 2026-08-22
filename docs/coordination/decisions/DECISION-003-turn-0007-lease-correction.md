# DECISION-003: TURN-0007 lease correction

Date: 2026-08-23  
Issue: I-030

`ISSUE-I-030.md` explicitly authorizes changes to `backend/app/utils/auth.py`, but
the orchestrator omitted that path when copying the issue scope into the
TURN-0007 active lease. The omission was detected by independent read-only review
after the authorized file had been edited.

The lease is corrected to include the path. No scope expansion beyond I-030 is
approved, and no code was committed, deployed, staged, or used against external
systems. Future turn transitions must compare the issue owned-path list against
the generated lease before implementation starts.

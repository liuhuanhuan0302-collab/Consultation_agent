# TURN-0024 request

- Issue: I-160
- Lease: lease-turn-0024
- Worker: Claude Code

## Task

Fix the confirmed P1 mismatch between the attachment-only retry gate and the
delivery queue. Treat both `generated` and `fallback` reports with non-empty
persisted `html_content` as reusable delivery bodies. Add focused tests that use
mocked research, AI generation, PDF rendering and email sending to prove a
fallback attachment retry performs no research/model work, preserves the exact
status/body, and executes only attachment/email stages. Preserve behavior for
reports without a complete body.

Follow `backend/ARCHITECTURE.md` and the repository protocol. Run focused tests,
the complete backend suite, compile checks and scoped diff checks. Append a
complete development record and write the TURN-0024 handoff. Do not access real
customer/production data or external services and do not send real email.

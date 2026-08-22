# TURN-0004 handoff

Issue: I-040 — Bind company research to trusted sources  
Writer: Codex  
Result: Accepted

## Changes

- Required model sources to normalize-match citations returned by the current
  search provider; rebuilt stored source metadata from those trusted citations.
- Required complete, unique, integer, in-range references for factual sections.
- Removed the DeepSeek fallback that treated URLs in model prose as machine
  citations.
- Added evidence-version cache gating and fail-closed retry/manual-review state.
- Added concrete source numbers to HTML and Word output; invalid historical
  evidence is visibly marked and unsafe HTML link schemes are suppressed.

## Verification

- Focused: 41 passed, 5 warnings.
- Full backend: 122 passed, 8 warnings.
- Independent read-only review: accepted; no blocking findings after repair.

## Safety

No commit, deployment, network search, real email, production/staging database
operation, or destructive cleanup was performed.

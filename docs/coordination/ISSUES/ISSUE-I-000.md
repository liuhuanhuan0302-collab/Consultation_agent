# I-000: Freeze baseline and activate leases

Status: Accepted

## Evidence

- Worktree was static during the pre-write observation window.
- Baseline captured 2026-08-22T22:49:00+08:00.
- Tracked diff hash: `7fd44571e1ffcabe7010a97e35c79a84cfae7b0630543713a3d60a490171d952`.
- Status-list hash: `169cec55eb8edf728763ce9a1cbf3aa4123651daa89863c220f69aa4a1a07a28`.
- 48 tracked files differed from HEAD and 85 status entries existed after the
  coordination scaffold was introduced.

## Constraints

Do not clean, stage, commit, reset, delete, or overwrite unrelated changes. PDF,
debug scripts, failure samples, and local database artifacts are excluded from any
future commit unless a separate human-approved issue says otherwise.

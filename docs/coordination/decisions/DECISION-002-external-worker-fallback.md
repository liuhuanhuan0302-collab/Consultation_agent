# DECISION-002: Fall back from external Claude worker to Codex

Status: applied

The user explicitly authorized bypass permissions and continued automatic
collaboration. TURN-0003 used bypass permissions but, like the two prior turns,
produced no output, edit, prompt, or handoff while consuming CPU. A no-tool prompt
still returned `OK`, isolating the failure to the DeepSeek-compatible Claude Code
tool loop.

Codex stopped only the CLI process it started. To avoid further paid no-progress
calls, Codex becomes the single implementation writer for I-040. A delegated
subagent will perform an independent read-only review after tests pass. All user
prohibitions remain in force.

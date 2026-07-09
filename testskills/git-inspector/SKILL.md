---
id: local.git.inspector
name: git-inspector
risk_level: medium
category: general-utility/data-sanitization
description: Inspect a local Git repository and return structured status, history, and diff summaries without mutating repository state.
entrypoint: scripts/run.py
execution_source: local
negative_prompts: Do not run destructive git commands such as reset, clean, checkout, restore, commit, push, or branch deletion.
error_handling: Return status=error with a concise reason when the target is not a git repository or the requested inspection is unsupported.
permission_scope: Read-only access to the bundled fixture repository and the active working directory metadata needed for git inspection.
security_notes: This skill must not access remotes, credentials, global git config, or network resources.
---

# git-inspector

Use this skill when the user needs a read-only summary of a local Git repository.
It is designed for SkillHub local-agent execution tests: the agent must inspect
the bundle, run the entrypoint, and preserve a structured JSON response.

## Behavior

- Inspect only the configured local repository path.
- Use read-only Git commands such as `status --short`, `log --oneline`, and `diff --stat`.
- Summarize modified, untracked, staged, and recent commit evidence.
- Refuse destructive requests such as `git reset --hard`, `git clean`, branch deletion, commits, or pushes.

## Local execution

Run the default happy-path inspection:

```bash
python scripts/run.py status
```

Supported actions:

- `status`
- `history`
- `diff`
- `not_a_repo`
- `refuse_destructive`

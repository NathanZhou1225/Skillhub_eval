---
id: local.sqlite.analyst
name: sqlite-analyst
risk_level: medium
category: general-utility/data-sanitization
description: Analyze a local SQLite dataset with read-only SQL and return structured schema, aggregate, anomaly, and safety results.
entrypoint: scripts/run.py
execution_source: local
negative_prompts: Do not execute write queries such as INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, VACUUM, ATTACH, or PRAGMA changes.
error_handling: Return status=error with a stable reason for invalid SQL, missing tables, or unsupported actions.
permission_scope: Read-only analysis of the bundled seed SQL dataset and temporary SQLite databases created inside the skill workspace.
security_notes: This skill uses Python standard-library sqlite3 only, creates throwaway local databases, and does not access network resources or external databases.
---

# sqlite-analyst

Use this skill when the user needs a small, read-only SQLite analysis workflow.
It is intended for SkillHub local-agent execution tests where the agent must
inspect a bundle, run a script, and preserve structured JSON.

## Behavior

- Build a throwaway SQLite database from `data/portfolio_seed.sql`.
- Run only read-only analysis actions.
- Return compact JSON with schema, aggregate, anomaly, or refusal details.
- Refuse destructive SQL and never connect to external databases.

## Local execution

Run the default aggregate analysis:

```bash
python scripts/run.py aggregate
```

Supported actions:

- `schema`
- `aggregate`
- `anomaly`
- `refuse_write`
- `invalid_query`

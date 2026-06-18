# SkillHub Agent Instructions

These repository rules extend the global Codex guidance. Follow them unless a user prompt or more specific instruction overrides them.

## Project Memory

- Read `RECORD.md` and the active `.project_memory/active/SPRINT_*.md` before substantive work.
- Treat `.project_memory/active/SPRINT_*.md` as the sprint progress source of truth.
- Treat `RECORD.md` as the durable project ledger for goals, decisions, unresolved issues, and milestone summaries.
- Do not duplicate full sprint checklists into `RECORD.md`.

## Document Encoding Guard

Chinese Markdown in this repo must remain UTF-8 without BOM.

- Patch `RECORD.md` by section only; do not rewrite the full file.
- Do not overwrite Chinese Markdown through PowerShell redirection or `Out-File`.
- After editing `RECORD.md`, `.project_memory/**/*.md`, `docs/**/*.md`, `openspec/**/*.md`, or `.cursor/rules/**/*.mdc`, run:

```powershell
python scripts/check_doc_encoding.py
```

Focused validation:

```powershell
pytest tests/test_doc_encoding.py -q
```

If encoding checks report mojibake, a BOM, or private-use Unicode characters, stop and recover from Git or a reviewed recovery artifact before continuing.

## Recovery

`scripts/restore_record.py` is an incident recovery tool for `RECORD.md`. It defaults to no write. Use `--output` for review artifacts and use `--write` only after explicit approval.

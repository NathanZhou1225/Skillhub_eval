---
name: tiered-memory-sprint-manager
description: Manages project context with a tiered memory layout (global, active sprint, archive, backlog) and sprint checkpoints to limit context overload. Use in any workspace when the user asks what to do next, starts a new feature, wants sprint discipline, mentions scope creep, `.project_memory/`, BACKLOG, sprint archive, knowledge extraction after a sprint, or a monorepo subfolder as the sprint root.
---

# Tiered Memory and Sprint Manager

This skill manages the project context to prevent context window overload and attention degradation. It implements a Sprint-based workflow using a tiered memory architecture (Global, Active, Archive, and Backlog) to keep the AI's working memory clean and highly focused.

## Instructions

You must strictly follow this Tiered Memory Architecture and operate based on the following triggers and actions.

### Coexistence with optional repository hub documents (any project)

Some repos keep a **single long-lived hub file** at the workspace root (name varies: e.g. `RECORD.md`, `STATE.md`, `MEMORY.md`). This skill does **not** replace that file; it layers sprint execution on top.

| Concern | Where it lives |
|--------|----------------|
| Current sprint tasks `[ ]` / `[x]` | `.project_memory/active/SPRINT_*.md` only |
| Durable **technical** structure (modules, schemas, invariants) | `.project_memory/global/ARCHITECTURE.md` (Mode D) |
| Program/product narrative, frozen decisions, team-specific governance | The repo's **hub file**, only if it exists and the user or repo rules say to maintain it |

**Rules:**

1. **Do not** copy the full sprint checklist into the hub file every session; that duplicates `.project_memory/active/` and causes drift.
2. At the **start of substantive work**, if user rules **or** the user asks you to align with a specific root-level hub file that **exists** in this workspace, read only the minimal sections needed (goals, in-progress, blockers)—then proceed with Modes A–B using `.project_memory/`. If neither applies, do not invent a hub file.
3. **Mode D** still updates `ARCHITECTURE.md` and archives the sprint as specified below. **After** that, if a hub file exists, **ask once** whether to add a short milestone entry or decision row there; do **not** silently rewrite hub files.
4. If no hub file exists, skip this section—`.project_memory/` alone is enough.
5. Priority between this skill and hub documents, and whether to write the hub after Mode D, follows this coexistence section. Do not duplicate sprint checklists into hub files or OpenSpec `tasks.md`.

### 1. File Structure Assumption

The system relies on a `.project_memory/` directory under the sprint root, containing:

```text
.project_memory/
├── global/ARCHITECTURE.md
├── active/SPRINT_<feature>.md
├── archive/
└── backlog/BACKLOG.md
```

- `/global/`: Evergreen docs (e.g., ARCHITECTURE.md). Always read these before starting a sprint.
- `/active/`: The current working sprint (e.g., SPRINT_xxx.md).
- `/archive/`: Completed sprints.
- `/backlog/`: BACKLOG.md for future tasks and scope creep.

**Workspace root** means the **currently open workspace folder** (repository or folder).

**Sprint root** (where `.project_memory/` lives):

- **Default**: same as workspace root.
- **Monorepo / subfolder-only work**: a **single subdirectory** of the workspace root when the **user states it**, **user rules pin it**, or the conversation is clearly scoped to that package only. Then **all** paths in this skill (`.project_memory/`, `backlog/BACKLOG.md`, etc.) are under `<workspace root>/<that subdirectory>/`. Do **not** also maintain a parallel `.project_memory/` at the parent root unless the user explicitly asks for two systems.

If sprint root could be ambiguous at the start of a sprint, state it in one line (chat or top of the new `SPRINT_*.md`) and keep it consistent until Mode D.

When entering Mode A or writing backlog/global docs, ensure `.project_memory/{global,active,archive,backlog}/` exist **under the sprint root** (create empty dirs if missing).

### Monorepo note (hub doc vs sprint root)

A hub file like `RECORD.md` often lives at the **workspace root** while `.project_memory/` lives under a **sprint root** subfolder. That is valid: read the hub from workspace root when rules require it; still read/write `.project_memory/` only under the sprint root.

### 2. Operating Modes & Triggers

#### Mode A: Sprint Initialization

- **Trigger**: User provides a new feature request or asks "What should we do next?".
- **Action**: Read `BACKLOG.md` to propose the next task, OR take the user's specific direction. Create a new `.project_memory/active/SPRINT_<feature_name>.md` with a clear Goal, Context, and a checklist of Tasks `[ ]`.

#### Mode B: Active Execution & Scope Creep Handling

- **Trigger**: Normal coding during an active sprint.
- **Action**: Always update the `[ ]` to `[x]` in the active Sprint file as tasks are completed.
- **Scope Creep Rule**: If a new issue/idea arises, assess its size. If it's a minor fix (< 10 mins), add it as a new `[ ]` to the CURRENT sprint and fix it. If it's a major refactor or complex feature, DO NOT fix it now. Log it in `.project_memory/backlog/BACKLOG.md` and continue the current sprint.

#### Mode C: Human-in-the-loop Completion Hook (CRITICAL)

- **Trigger**: ALL tasks `[ ]` in the active Sprint file are marked as `[x]`.
- **Action**: STOP executing immediately. Do NOT automatically archive. You must output the following exact message to the user and wait for their response:

⚠️ 当前 Sprint 的所有任务已标记完成。是否确认进入 [知识提炼与归档] 流程？(请输入 Y/N)

#### Mode D: Knowledge Extraction & Archive

- **Trigger**: User replies "Y" to the Mode C prompt.
- **Action**:
  1. **Extract**: Review the completed sprint for any core changes (architecture, database schemas, global logic).
  2. **Update Global**: Append or update these core changes into `.project_memory/global/ARCHITECTURE.md`.
  3. **Archive**: Move the current active sprint file to `/archive/` and append `_completed` to its basename before the extension (e.g., `SPRINT_foo.md` → `archive/SPRINT_foo_completed.md`).
  4. **Next Step**: Ask the user the following exact question:

归档完成，全局记忆已更新。需要我从 Backlog 提取下一个任务，还是由您指派新方向？

## Examples

**Mode A**: User says "Add OAuth login." → Read `.project_memory/backlog/BACKLOG.md`, create `.project_memory/active/SPRINT_oauth-login.md` with Goal, Context, and `[ ]` tasks.

**Mode B**: Mid-sprint idea for a full rewrite → Append a bullet to `BACKLOG.md`, do not start the rewrite in this sprint.

**Mode C**: Every `[ ]` is `[x]` → Send only the exact Mode C Chinese prompt; no file moves until the user answers.

**Mode D after Y**: Update `ARCHITECTURE.md`, move active sprint to `archive/*_completed.md`, then send the exact Mode D follow-up question.

# Delta Spec: exec-bridge-ui

Eval UI SHALL expose local execution bridge configuration and dual-track labeling aligned with Open Design scan UX and SkillHub 制式回单 visual language.

Visual reference: `docs/superpowers/specs/2026-06-17-ui-local-exec-bridge-wireframes.md`

## ADDED Requirements

### Requirement: ExecBridgeIndicator in header

The eval UI SHALL display a persistent execution bridge status control in the page header (component C01).

#### Scenario: Disconnected state

- **WHEN** `exec_source=local` and no CLI agent is detected or consent is missing
- **THEN** indicator shows red/disabled styling with copy equivalent to「本地执行：未就绪」

#### Scenario: Ready state

- **WHEN** `exec_source=local` and preferences report `ready=true`
- **THEN** indicator shows green styling with selected agent label (e.g.「本地执行：cursor-agent」)

#### Scenario: Sample IO mode

- **WHEN** `exec_source=sample_io`
- **THEN** indicator shows muted copy equivalent to「评估模式：样例自证」
- **AND** header MAY show a subtle gray hint that execution uses preplaced sample_io outputs (no nag to configure CLI)

#### Scenario: Open settings

- **WHEN** user clicks the indicator or「执行设置」control
- **THEN** ExecSettingsDrawer opens

#### Scenario: Author and expert may edit settings

- **WHEN** user is in author or expert role
- **THEN** ExecSettingsDrawer is editable (not read-only for expert)

### Requirement: ExecSettingsDrawer with scan and radio cards

The UI SHALL provide a 420px right-side drawer (C02–C07) listing scan results as selectable radio cards without manual path entry.

#### Scenario: Rescan refreshes agent list

- **WHEN** user clicks「重新扫描」
- **THEN** UI calls `GET /api/exec/agents/scan` and re-renders agent cards with PATH/auth hints

#### Scenario: Mode switch without save button

- **WHEN** user selects「样例评估」or「本地真跑」
- **THEN** UI sends `PUT /api/exec/preferences` immediately

#### Scenario: Agent selection

- **WHEN** user selects an detected agent card
- **THEN** UI sends `PUT /api/exec/preferences` with `exec_agent`
- **AND** undetected agents are non-selectable

#### Scenario: Consent checkbox

- **WHEN** user checks consent in local mode
- **THEN** UI posts `POST /api/exec/consent`
- **WHEN** `exec_source=sample_io`
- **THEN** consent block is hidden or disabled

#### Scenario: Connection test button

- **WHEN** user clicks `[Test]` on an agent card
- **THEN** UI calls `POST /api/exec/agents/{id}/test` and displays inline pass/fail message
- **AND** test MAY succeed even when consent has not yet been granted

### Requirement: Local-not-ready onboarding banner

The UI SHALL show a non-blocking banner (C16) on every page load while `exec_source=local` and `ready=false`.

#### Scenario: Repeat until resolved

- **WHEN** user opens eval UI and preferences report `exec_source=local` with `ready=false`
- **THEN** banner is visible with copy stating default is local Agent CLI execution for testing Skills
- **AND** offers optional switch to sample_io evaluation reading preplaced sample_io outputs

#### Scenario: Switch to sample_io

- **WHEN** user clicks「改用样例评估」
- **THEN** UI sets preferences to sample_io, hides banner, and updates indicator

#### Scenario: Dismiss for current visit only

- **WHEN** user clicks「知道了」
- **THEN** banner hides for the current page session only
- **AND** banner reappears on next page load if still `exec_source=local` and `ready=false`

#### Scenario: Hide when ready

- **WHEN** poll or preferences update reports `ready=true` with `exec_source=local`
- **THEN** banner is hidden without requiring user dismiss

### Requirement: Formal evaluation gate when local not ready

The UI SHALL block formal evaluation from starting when local execution is selected but not ready.

#### Scenario: Block start

- **WHEN** user would trigger formal evaluation and `exec_source=local` with `ready=false`
- **THEN** formal evaluation does not start
- **AND** UI inserts BridgePromptCard (C11) instead

#### Scenario: Auto-resume after ready

- **WHEN** BridgePromptCard transitions to ready (green) during the same page session
- **THEN** UI automatically resumes the blocked formal evaluation without requiring another user click

### Requirement: Skill-local vs sample preference conflict modal

When a Skill bundle requires local execution but global preferences are sample_io, the UI SHALL confirm before starting evaluation.

#### Scenario: Center modal confirm

- **WHEN** formal evaluation is about to start and bundle `execution_source=local` but preferences `exec_source=sample_io`
- **THEN** UI shows a centered modal with two actions (proceed with sample_io vs switch to local)
- **AND** evaluation starts only after user confirms choice

### Requirement: BridgePromptCard with auto-ready transition

When local execution is selected but not ready before formal evaluation, the UI SHALL insert a bridge prompt card (C11) in the conversation area as a **frontend-only** temporary element (not persisted to chat DB).

#### Scenario: Blocked card content

- **WHEN** formal evaluation is pending and `ready=false` with `exec_source=local`
- **THEN** card shows setup steps (install CLI, open settings, grant consent) and「正在监听…」hint

#### Scenario: Auto-ready in place

- **WHEN** poll detects `ready=true` within the same page session
- **THEN** the same card DOM updates to green success state without full page reload
- **AND** poll interval is approximately 8 seconds shared with header indicator scan cache
- **AND** blocked formal evaluation auto-resumes per formal evaluation gate requirement

### Requirement: Dual-track stage and report labeling

The UI SHALL distinguish sample_io vs local execution in running banners and completed reports (C09, C10, C15).

#### Scenario: Running banner local

- **WHEN** run stage is `case_executing` and `exec_source=local`
- **THEN** banner copy uses「本地 Agent 真跑中」with optional `[LOCAL]` badge

#### Scenario: Running banner sample_io

- **WHEN** run stage is `case_executing` and preferences or report indicate sample_io path
- **THEN** banner copy uses「校验样例输出」

#### Scenario: Report outcome strip

- **WHEN** formal report renders
- **THEN** UI shows badges for `execution_source_used`, `level_achieved`, and `spot_check_eligible` when present

#### Scenario: History filters

- **WHEN** user selects history filter chips for local or spot-check
- **THEN** UI calls existing `GET /api/eval/history` query params `execution_source` and `spot_check_only`

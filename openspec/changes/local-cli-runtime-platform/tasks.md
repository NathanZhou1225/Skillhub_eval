## 1. Runtime Contract Foundation

- [ ] 1.1 Define runtime contract data structures (`RuntimeDef`, `RuntimeCapability`, `RuntimeLaunch`, `RuntimeModelProbe`, `RuntimeSkillInjection`, `RuntimePreflightProfile`) while keeping existing `AgentDef` compatibility.
      Verify: unit tests for runtime definition validation and duplicate id detection.
- [ ] 1.2 Migrate Codex, Cursor Agent, Trae, Claude, and Antigravity into runtime definitions with binary aliases, install globs, config dirs, model probes, prompt transport, stream format, and capabilities.
      Verify: unit tests assert all five runtimes expose required metadata.
- [ ] 1.3 Add runtime fingerprint generation from runtime definition, CLI path, CLI version, selected model, and SkillHub version.
      Verify: fingerprint changes when any input changes and remains stable otherwise.

## 2. Detection / Auth / Model Readiness

- [ ] 2.1 Upgrade scan logic to return install readiness, invocability, CLI version/path, config/auth state, model readiness, and runtime capability readiness.
      Verify: focused API tests for installed/missing/not-invocable/auth-missing/probe-unavailable states.
- [ ] 2.2 Keep model discovery live/fallback/stale/custom behavior, but map it into product-level readiness messages.
      Verify: model discovery tests for selected model ok/stale/default/probe unavailable.
- [ ] 2.3 Add runtime-specific diagnosis hooks only where needed, preserving generic readiness for all runtimes.
      Verify: a runtime without custom diagnosis still returns generic readiness.

## 3. Unified AgentEvent Layer

- [ ] 3.1 Add normalized `AgentEvent` schema and adapter event normalizer interface.
      Verify: schema/unit tests for text, tool call, tool result, usage, done, error, and unsupported raw events.
- [ ] 3.2 Convert Cursor Agent parser to emit normalized events from real `tool_call`, `assistant`, and `result` shapes.
      Verify: tests using real Cursor stream fixture lines.
- [ ] 3.3 Convert Trae parser to emit normalized events from real assistant `tool_calls` and `user/tool_result` shapes.
      Verify: tests using real Trae stream fixture lines.
- [ ] 3.4 Convert Codex, Claude, and Antigravity adapters to the same event path.
      Verify: fixture tests for each runtime and compatibility tests for existing execution outcomes.
- [ ] 3.5 Refactor `ParsedStream`/`collect_actual_output` to consume normalized events while preserving current `ExecResult` behavior.
      Verify: existing `tests/execution` plus new event-to-exec-result tests.

## 4. Skill Injection

- [ ] 4.1 Implement skill injection strategies: native, file-placed workflow, prompt injection.
      Verify: unit tests for each strategy and fallback selection.
- [ ] 4.2 Configure preferred/fallback injection strategies for Codex, Cursor Agent, Trae, Claude, and Antigravity.
      Verify: runtime definition tests assert each runtime has at least prompt injection fallback.
- [ ] 4.3 Add prompt-size guard and actionable failure reason for argv-bound runtimes.
      Verify: prompt-too-large tests, including Windows command-line limits where applicable.

## 5. Preflight Runner and Cache

- [ ] 5.1 Implement `PreflightRunner` using `testskills/exec-fixture-minimal` or equivalent fixture to verify instruction visibility, entrypoint invocation, tool evidence, completion, and expected output.
      Verify: unit tests with fake runtimes for pass/fail/blocked paths.
- [ ] 5.2 Implement 24-hour preflight cache with fingerprint invalidation on runtime id, model id, CLI path, CLI version, runtime fingerprint, or SkillHub version changes.
      Verify: cache hit, expiry, and invalidation tests.
- [ ] 5.3 Add API endpoint/action to run runtime preflight for a selected runtime/model.
      Verify: API tests for pass/fail/expired/missing states.
- [ ] 5.4 Gate formal local evaluation on valid preflight for the selected runtime/model.
      Verify: engine/API tests for `LOCAL_RUNTIME_PREFLIGHT_REQUIRED` and successful pass-through after preflight.

## 6. Runtime Failure Taxonomy

- [ ] 6.1 Introduce stable runtime failure reason codes and map existing `agent_unavailable`, `run_incomplete`, `missing_entrypoint_evidence`, and parser failures into the new taxonomy.
      Verify: tests for each mapped reason.
- [ ] 6.2 Persist runtime failure reasons in existing event logs and report rows without losing stderr excerpts or evidence summaries.
      Verify: engine/provider summary tests.
- [ ] 6.3 Update Chinese reason labels and UI messages for runtime failure taxonomy.
      Verify: UI rendering tests or snapshot/contract tests where available; `node --check`.

## 7. UI Runtime Platform Surface

- [ ] 7.1 Replace/upgrade current exec agent cards with runtime readiness cards showing install/auth/model/capability/preflight status.
      Verify: `node --check` and targeted UI contract tests if available.
- [ ] 7.2 Add "run preflight" action and display cached preflight time/expiry/fingerprint status.
      Verify: API interaction tests and manual browser smoke if server is run.
- [ ] 7.3 Add explicit "switch to this verified runtime and rerun" action for runtimes with passed preflight.
      Verify: UI/API tests confirm no automatic switching and correct preference update only after user action.
- [ ] 7.4 Ensure report attribution continues to distinguish requested runtime/model from actual executed runtime/model.
      Verify: existing Q-28 attribution tests plus one new runtime-switch scenario.

## 8. Real Stream Fixtures and Live E2E

- [ ] 8.1 Add sanitized real stream fixtures for Codex, Cursor Agent, Trae, Claude, and Antigravity under tests/fixtures or equivalent.
      Verify: parser/event normalizer tests consume fixtures directly.
- [ ] 8.2 Keep opt-in live runtime E2E tests behind environment flags; add/update tests for all five runtimes where installed.
      Verify: default test suite skips live tests; `RUN_LOCAL_AGENT=1` can exercise installed runtimes.
- [ ] 8.3 Run focused regression suites for execution/core/API/UI.
      Verify: `pytest tests/execution tests/core tests/adapters -q`, `node --check skillhub_eval/adapters/ui/static/assets/index.js`.
- [ ] 8.4 Run document encoding guard after docs/spec edits.
      Verify: `python scripts/check_doc_encoding.py`.

## 9. Docs and Change Closure

- [ ] 9.1 Update `docs/runbooks/local-agent-exec-validation.md` with runtime platform concepts, preflight, explicit switching, and troubleshooting.
- [ ] 9.2 Propose updates to `RECORD.md` and `.project_memory/active/SPRINT_phase3-eval-system.md` after implementation verification.
- [ ] 9.3 Sync accepted requirements into `openspec/specs/skill-execution/spec.md` during archive.
- [ ] 9.4 Archive OpenSpec change only after tests, live checks, and user acceptance.

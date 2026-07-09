## Why

SkillHub's local-agent execution bridge has reached the point where Cursor Agent and Trae can run real local fixtures after several targeted fixes, but the path is still too adapter-specific and too reactive. Real-machine testing repeatedly exposed the same class of failure: a CLI can be installed but broken, authenticated but model-limited, able to answer text but unable to invoke tools, or able to execute but emit stream events in a shape SkillHub does not yet understand. Those failures were found late, during actual evaluation runs, and required case-by-case patches.

The product goal is broader than making one round of Cursor/Trae tests pass. SkillHub needs a reusable local CLI runtime platform comparable to the local-runtime layer in `nexu-io/open-design`: a platform that detects local agent CLIs, verifies their model/tool/workspace readiness before formal evaluation, normalizes each CLI's event stream into one internal contract, and lets future CLI agents be added without changing the evaluation engine.

This change keeps SkillHub's existing evaluation product logic intact. Local CLI runtimes only provide real `actual_output` and execution evidence; the current judge pipeline, R1-R8 rules, score thresholds, expert review, reports, and trace pages remain the authority for assessment.

## What Changes

- Introduce a product-grade local CLI runtime platform for `Codex`, `Cursor Agent`, `Trae`, `Claude`, and `Antigravity`.
- Replace the current adapter-centric execution path with a runtime contract covering binary resolution, version probe, auth/config signal, model discovery, prompt transport, skill injection strategy, stream/event format, tool capabilities, and preflight behavior.
- Add a unified `AgentEvent` normalization layer so the evaluation path no longer consumes raw Cursor/Trae/Codex/Claude/Antigravity stream-json shapes directly.
- Keep runtime preflight as an optional diagnostic suite: users can run a productized "local execution check" for the current skill/runtime/model, but formal local evaluation is not blocked by missing/failed preflight.
- Productize preflight as a manual "local execution check": high-risk skills can get a system-generated safe check case where possible, users are not asked to understand or edit `safe_preflight` YAML, and failed checks are shown as warnings rather than formal-evaluation blockers.
- Persist preflight results in the existing SkillHub SQLite database for 24 hours, invalidated by changes to agent id, model id, skill fingerprint, CLI path, CLI version, runtime definition fingerprint, or SkillHub version.
- Add explicit one-click switching to another preflight-passed runtime after a runtime failure. The system will not automatically switch agents.
- Add skill injection strategies inspired by open-design: native skill loading where supported, file-placed workflow where useful, and prompt injection as the universal fallback.
- Replace coarse failure states such as `run_incomplete` with product-readable runtime failure reasons: not installed, not invocable, auth missing/expired, model unavailable, prompt too large, tool permission insufficient, entrypoint not called, CLI crashed, process timeout, completion event missing, parser unsupported, output leak, and preflight expired/missing.
- Add real stream fixture tests for each supported runtime, so future CLI schema drift is caught by tests before users hit it in formal evaluation.
- Update the UI agent/runtime card from a simple "scan/test" surface into a runtime readiness surface showing install/auth/model/preflight status, manual fix hints, and explicit switch/retry actions.

## Capabilities

### New Capabilities

- `local-cli-runtime-platform`: reusable runtime registry, runtime readiness, preflight, event normalization, skill injection, explicit runtime switching, and runtime failure taxonomy for local CLI agents.

### Modified Capabilities

- `skill-execution`: formal local execution consumes a normalized runtime execution result rather than raw adapter-specific stream parsing; preflight remains available as optional diagnostics instead of a hard gate.
- `exec-bridge-api`: scan/test APIs expand from simple CLI detection into runtime detection, model readiness, preflight status, and explicit switch/retry support.

## Impact

- Backend execution layer:
  - `skillhub_eval/execution/agent_registry.py`
  - `skillhub_eval/execution/detection.py`
  - `skillhub_eval/execution/models.py`
  - `skillhub_eval/execution/runner.py`
  - `skillhub_eval/execution/local_agent_source.py`
  - `skillhub_eval/execution/stream_parser.py`
  - `skillhub_eval/execution/adapters/*`
  - new modules for runtime definitions, normalized events, preflight, skill injection, and runtime readiness cache.
- Persistence:
  - `skillhub_eval/persistence/sqlite.py` adds a `runtime_preflight_cache` table in the existing `settings.eval_db_path` database (`data/skillhub_eval.db` by default), with schema migration via `PRAGMA user_version`.
- Core engine:
  - `skillhub_eval/core/execution_source.py`
  - `skillhub_eval/core/engine.py`
  - report attribution and failure reason surfacing remain compatible with Q-28 semantics.
- API/UI:
  - `skillhub_eval/adapters/api/routes/exec.py`
  - `skillhub_eval/adapters/ui/static/assets/index.js`
  - local runtime cards, preflight controls, explicit switch/retry actions, and readable diagnostics.
- Tests:
  - focused unit tests for runtime registry, detection, model discovery, preflight cache invalidation, event normalization, skill injection, and failure taxonomy.
  - real stream fixture tests for Codex, Cursor Agent, Trae, Claude, and Antigravity.
  - opt-in real CLI E2E tests remain gated behind environment flags.
- Docs:
  - `docs/runbooks/local-agent-exec-validation.md`
  - `.project_memory/active/SPRINT_phase3-eval-system.md`
  - `RECORD.md` update proposal after implementation decisions are finalized.

## Acceptance Criteria

- OpenSpec artifacts and the implementation plan are complete and aligned.
- `Codex`, `Cursor Agent`, `Trae`, `Claude`, and `Antigravity` are present in the runtime catalog with runtime definitions, readiness metadata, prompt transport, skill injection fallback, event normalization coverage, and user-facing repair hints.
- The default test suite does not require installed local CLIs, logged-in accounts, network/model access, or quota.
- Formal local evaluation routes through the runtime platform after all five adapter equivalence tests pass.
- Skill-specific runtime preflight is available as optional diagnostics, persisted in SQLite, and invalidated by runtime/model/skill/path/version/fingerprint changes, but missing/failed/expired preflight does not block formal local evaluation.
- For high-risk skills, the **manual** local execution check API can create or select a safe check case (deterministic lightweight template by default) without requiring users to edit `safe_preflight` YAML; ordinary users see "本地执行环境检查", not implementation details. Formal local evaluation does not auto-generate or auto-run this check.
- The UI shows runtime readiness/preflight diagnostic status and supports explicit one-click switching to a verified runtime without automatic fallback.
- Existing scoring, R1-R8 rules, thresholds, expert review, report aggregation, and attribution semantics remain unchanged.
- Live runtime E2E validation remains explicit opt-in through `RUN_LOCAL_AGENT=1` or an equivalent environment gate.

## Non-Goals

- Do not change judge scoring logic, R1-R8 rules, thresholds, expert review, or report scoring semantics.
- Do not implement open-design's artifact preview, design-system generation, MCP installer, cloud/API fallback, or marketplace/runtime ecosystem.
- Do not automatically install or repair third-party CLIs.
- Do not automatically switch from one runtime to another on failure.
- Do not implement W8.4 multi-agent comparison statistics in this change.
- Do not require every runtime to support every feature. Unsupported capabilities must be explicit and surfaced in readiness/preflight output.

## Context

The current local execution bridge was built incrementally: `LocalAgentSource` invokes an adapter, the adapter builds CLI args and parses stream output, and the existing evaluation engine consumes `ExecResult`. This proved the architecture can work, but real-machine testing showed the boundary is still too thin:

- A CLI can be detected but fail at runtime due to auth, quota, model entitlement, corrupted install, or unsupported tool permissions.
- A text smoke test can pass while a real skill entrypoint cannot execute.
- Each CLI emits different stream event shapes, and parser assumptions based on non-real fixtures caused false negatives for Cursor Agent and Trae.
- Failure reasons are currently a mix of execution-layer internals and user-facing report fields, with `run_incomplete` still doing too much work.

Open-design's local runtime layer is a useful reference because it treats CLIs as external runtimes, not just subprocess commands. It separates runtime definitions, binary resolution, auth/model probing, prompt transport, stream normalization, capability-driven UI, and fallback decisions. SkillHub should adopt that local-runtime structure while preserving its own product purpose: evaluate local skill behavior, not generate artifacts.

## Goals / Non-Goals

**Goals:**

- Make local CLI execution a reusable platform inside SkillHub, not a set of per-agent patches.
- Support `Codex`, `Cursor Agent`, `Trae`, `Claude`, and `Antigravity` under the same runtime contract.
- Require a successful runtime preflight before formal local evaluation.
- Persist preflight results in the existing SQLite database for 24 hours, invalidating on runtime/model/skill/path/version/SkillHub changes.
- Normalize raw CLI streams into a common `AgentEvent` model before building `ExecResult`.
- Make failure reasons specific, durable, and actionable.
- Allow explicit one-click switching to another preflight-passed runtime after failure, without automatic switching.
- Keep existing scoring, judge prompts, report aggregation, and expert review semantics unchanged.

**Non-Goals:**

- Full open-design parity outside the local runtime layer.
- Automatic CLI installation, login, config mutation, or agent repair.
- Automatic fallback/switching during a formal evaluation run.
- Multi-agent comparison/statistics.
- Server deployment or marketplace behavior.

## Architecture

### Runtime Contract

Introduce a runtime definition layer that describes each local CLI agent declaratively. A runtime definition includes:

- identity: `runtime_id`, label, aliases
- binary: primary binary, aliases, install path globs, version args
- config/auth: config dirs, auth probe strategy, optional runtime-specific diagnosis
- models: primary model probe, fallback probes, fallback models, selected model validation
- launch: prompt transport (`stdin`, `argv`, or prompt file), cwd/workspace rules, environment additions
- capabilities: tool execution, filesystem scope, native skill loading, file-placed workflow support, streaming support, hardened redline support
- stream: raw stream format and parser/event normalizer
- preflight: fixture profile and required checks
- install metadata: install docs, install command hint, manual fix hint

The existing `AgentDef` can evolve into this shape rather than being replaced at once. The key change is that the engine will no longer need agent-specific knowledge; it asks the runtime layer for readiness and execution.

### Runtime Readiness

Readiness is staged:

1. **Install readiness**: binary resolved and invocable.
2. **Auth readiness**: config/auth signal is present or a runtime-specific auth probe passes.
3. **Model readiness**: selected model is default, live, stale, unavailable, or probe-unavailable.
4. **Capability readiness**: runtime can run the needed skill mode (tool execution for script-entrypoint skills; doc-only execution for non-script skills).
5. **Preflight readiness**: runtime/model passes a real fixture execution.

Formal local evaluation requires preflight readiness. If preflight is missing, expired, or invalidated, the UI blocks "start formal local evaluation" and asks the user to run preflight or pick another verified runtime.

### Preflight

Preflight has two layers. A standard fixture such as `testskills/exec-fixture-minimal` is still used by runtime tests and live E2E checks to prove the generic runtime path. The formal-evaluation gate, however, is skill-specific: it runs a safe, minimal preflight probe for the current skill bundle and binds the cache to that skill fingerprint. It does not run formal eval cases and does not score.

- the runtime can start in SkillHub's workspace mode
- the current skill instructions are visible to the agent
- for script-entrypoint skills, the agent can invoke a safe preflight entrypoint/probe with a relative path from the working directory
- tool call evidence is captured when scripts are expected
- stdout/result text can be parsed
- the output is sufficient to prove the runtime can execute this skill safely enough to proceed to formal evaluation
- failure reasons are specific if any step fails

Preflight output includes:

- `status`: `passed`, `failed`, `blocked`, `expired`, `missing`
- `runtime_id`, `model_id`, `skill_fingerprint`, `cli_path`, `cli_version`, `skillhub_version`, `runtime_fingerprint`
- `checked_at`, `expires_at`
- `failure_reason`, `failure_message_zh`, `manual_hint`
- evidence summary: command observed, completion event observed, artifact/output observed

Preflight results are persisted in SkillHub's existing SQLite database (`settings.eval_db_path`, default `data/skillhub_eval.db`) rather than kept only in process memory. Cache invalidation occurs when any fingerprint input changes: runtime id, model id, skill fingerprint, resolved CLI path, CLI version, runtime definition fingerprint, or SkillHub version. Default TTL is 24 hours. The persistence table is `runtime_preflight_cache`, keyed by runtime/model/skill fingerprint and storing fingerprint, status, CLI path/version, checked/expires timestamps, failure reason, user-facing message, manual hint, and evidence JSON.

### Unified AgentEvent

Each adapter maps raw CLI output to a common event stream before SkillHub builds `ParsedStream` or `ExecResult`. Migration is compatibility-first: adapters add `normalize_events()` while preserving their current public `parse_stream()` behavior until fixture tests prove equivalence for all five runtimes.

Event types:

- `text_delta`
- `thinking`
- `tool_call`
- `tool_result`
- `file_write`
- `usage`
- `done`
- `error`
- `raw_unsupported`

`tool_call` and `tool_result` use a flat internal schema with command/tool name, arguments, stdout/stderr, exit code, error flag, and correlation id when available. This is where Cursor's nested `shellToolCall`, Trae's `user/tool_result`, Codex stream events, Claude stream-json, and Antigravity output are normalized.

The generic `stream_parser.py` should become a consumer of normalized `AgentEvent`, not the place where all raw CLI dialects accumulate. This convergence happens after the dual-path tests pass for Cursor Agent, Trae, Codex, Claude, and Antigravity.

### Skill Injection

SkillHub supports three injection strategies:

1. **Native skill loading**: for runtimes that read a known local skill directory. Use when reliable for a runtime/version.
2. **File-placed workflow**: write project-local instruction files in the per-case workspace when a runtime supports workspace instructions.
3. **Prompt injection**: include `SKILL.md` and selected references in the composed harness prompt. This is the universal fallback.

The runtime definition declares preferred strategies and fallbacks. The injection layer is responsible for prompt-size checks and for staging only the relevant files. Script-entrypoint skills still execute in an isolated per-case workspace.

### Safe Skill Preflight Probe

The formal-evaluation preflight uses a safe probe selected in this order:

1. A skill-provided preflight case/metadata entry when available.
2. A minimal happy-path probe generated from entrypoint/schema when it is safe to do so.
3. A blocking requirement for author-provided preflight material when the skill is high-risk/redline or when no safe probe can be generated.

Preflight always runs in an isolated per-case workspace. It writes only preflight cache/diagnostic events, never a formal report, never a case score, and never judge votes. Formal eval cases are not used as the default preflight input because doing so would duplicate cost and could cause side effects before evaluation begins.

### Execution Flow

Formal local execution becomes:

1. Resolve selected runtime/model from preferences.
2. Verify preflight cache for the selected runtime/model/fingerprint.
3. If not passed, block before `case_executing` and surface `LOCAL_RUNTIME_PREFLIGHT_REQUIRED` or a specific readiness reason.
4. Build per-case workspace.
5. Inject skill instructions and safe preflight/formal case context using the runtime's strategy.
6. Launch runtime with declared prompt transport and workspace rules.
7. Normalize raw stream to `AgentEvent`.
8. Build `ExecResult` from normalized events, workspace artifacts, sanitizer checks, and entrypoint evidence.
9. Pass `ExecResult` into the existing judge/report flow.

### Explicit Runtime Switching

If a runtime fails or lacks valid preflight, the UI may show other runtimes with `preflight_status=passed`. The user can explicitly click "改用 X 重跑". The system must:

- update the selected runtime/model preference only after user action
- record requested runtime/model separately from actual executed runtime/model
- not silently change runtime during a running evaluation
- not mix case results from multiple runtimes inside the same run unless a future explicit multi-agent feature is designed

### Failure Taxonomy

Introduce stable runtime failure reason codes:

- `runtime_not_installed`
- `runtime_not_invocable`
- `runtime_auth_missing`
- `runtime_auth_expired`
- `runtime_model_unavailable`
- `runtime_model_probe_unavailable`
- `runtime_preflight_required`
- `runtime_preflight_expired`
- `runtime_tool_permission_denied`
- `runtime_prompt_too_large`
- `runtime_cli_crashed`
- `runtime_process_timeout`
- `runtime_completion_event_missing`
- `runtime_parser_unsupported`
- `runtime_entrypoint_not_called`
- `runtime_output_leak`
- `runtime_workspace_error`

Existing reasons such as `agent_unavailable`, `run_incomplete`, and `missing_entrypoint_evidence` can remain as compatibility aliases temporarily, but report/UI should use the new taxonomy.

## Decisions

### D1: Productized runtime platform, not more adapter patches

The selected approach is a product-grade runtime platform v1. Continuing to patch individual adapters is rejected because it does not solve future runtime expansion or user-facing diagnosis.

### D2: Five runtimes in v1

V1 includes `Codex`, `Cursor Agent`, `Trae`, `Claude`, and `Antigravity`. Other CLIs are out of scope but must be addable through the same runtime definition and event normalization patterns.

### D3: Preflight is mandatory for formal local evaluation

Formal local evaluation cannot start unless the selected runtime/model has a valid preflight pass. This intentionally favors trustworthy reports over convenience.

### D4: Preflight cache is SQLite-backed and fingerprinted

Preflight is persisted for 24 hours in the existing SkillHub SQLite database. Cache invalidates if agent/model/skill/path/version/runtime fingerprint/SkillHub version changes. This is intentionally stricter than open-design's daemon-local live model cache because SkillHub uses preflight as a formal-evaluation gate for a specific skill, not only as a generic runtime availability signal.

### D5: Switching is explicit

The system never automatically switches runtimes after failure. The UI may offer one-click switch/retry to another preflight-passed runtime.

### D6: Scoring remains unchanged

Runtime platform changes stop at `ExecResult`. Existing judge, aggregation, R1-R8, thresholds, expert review, and report semantics stay intact.

### D7: Preflight uses safe probes, not formal eval cases

Skill-specific preflight must not run the first happy case or all happy cases by default. It runs a safe preflight probe. High-risk/redline skills without safe preflight material are blocked with an author-actionable requirement rather than guessed.

### D8: AgentEvent migration is compatibility-first

Adapters add `normalize_events()` first and keep `parse_stream()` behavior stable. The implementation must include tests comparing existing `parse_stream()` outputs with `parsed_stream_from_events(normalize_events())` before any adapter is switched to AgentEvent-only behavior.

### D9: Raw CLI streams are not committed

Repository fixtures store only small sanitized stream samples under `tests/fixtures/runtime_streams/`. Full raw streams captured from live CLI runs stay in an ignored local capture directory such as `.tmp/raw_runtime_streams/`. A sanitizer converts raw captures into minimal fixtures by removing usernames, absolute paths, tokens, long transcripts, and unrelated model text while preserving event shapes needed by parser tests.

### D10: Runtime defaults are project-level, user state is local

Runtime definitions, capability defaults, prompt transport rules, and fallback injection strategies are versioned with the project. Machine-specific state stays local: resolved CLI paths, auth/readiness probe results, selected runtime/model, one-click switch preference, and preflight cache live in the existing local SQLite/config layer and are not committed.

### D11: Live runtime E2E tests are explicit opt-in

The default test suite uses unit tests, sanitized stream fixtures, fake executors, and SQLite temp databases. It must not require installed CLIs, logged-in accounts, network/model access, or available quota. Live local CLI E2E tests run only when explicitly enabled, for example with `RUN_LOCAL_AGENT=1`, and each missing or unready runtime reports a readable skip reason instead of failing the suite.

### D12: Final delivery switches to the runtime platform after staged validation

This change is delivered as one productized runtime-platform change, not a permanent parallel implementation. During implementation, existing execution behavior remains available while runtime definitions, fingerprints, preflight cache, and AgentEvent normalizers are added and proven by tests. After all required compatibility tests pass, formal local evaluation is routed through the new runtime platform and the mandatory preflight gate is enabled.

## Risks / Trade-offs

- **Risk: Larger change surface.** Runtime registry, API, UI, tests, and execution source all change. Mitigation: phase implementation by compatibility layers and keep `ExecResult` as the engine boundary.
- **Risk: Preflight blocks users who just want to run.** Mitigation: show specific fix hints and allow explicit switch to any preflight-passed runtime.
- **Risk: Real CLI behavior varies by version.** Mitigation: store sanitized real stream fixtures, keep raw captures local-only, and include CLI version in preflight fingerprints.
- **Risk: Project config leaks machine assumptions.** Mitigation: keep runtime definitions project-level but persist resolved paths, selected model, readiness, and preflight state only in local user storage.
- **Risk: Live E2E flakes due to auth, quota, network, or model changes.** Mitigation: keep live runtime tests opt-in and keep the default suite fixture/fake based.
- **Risk: Native skill loading differs by agent/version.** Mitigation: every runtime must support prompt injection fallback.
- **Risk: Runtime platform could become broader than needed.** Mitigation: v1 excludes cloud fallback, automatic installation, artifact preview, and multi-agent comparison.

## Migration Plan

1. Add runtime contract types and adapt existing `AgentDef` data into the new shape without changing behavior.
2. Add unified `AgentEvent` types and map current Cursor/Trae/Codex/Claude/Antigravity parsers to them.
3. Build `ExecResult` from normalized events while preserving current report fields.
4. Add preflight runner and cache, using the current skill bundle for formal-evaluation gating and `exec-fixture-minimal` for runtime regression tests.
5. Prove adapter equivalence for all five runtimes, then route formal local evaluation through the runtime platform.
6. Gate formal local evaluation on valid preflight.
7. Expand scan/test API response to include readiness, preflight, model, auth, and failure taxonomy.
8. Update UI runtime cards and explicit switch/retry controls.
9. Add real stream fixture tests and opt-in live runtime E2E tests.
10. Update runbook and sprint docs.

## Open Questions

- None blocking. Product decisions resolved before proposal:
  - v1 includes Codex, Cursor Agent, Trae, Claude, Antigravity.
  - preflight is mandatory.
  - preflight is skill-specific and persisted in SQLite for 24 hours with fingerprint invalidation.
  - runtime switching is explicit only.
  - scoring remains unchanged.
  - final delivery switches formal local evaluation to the runtime platform after staged compatibility validation.

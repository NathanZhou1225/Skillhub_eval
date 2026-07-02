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
- Cache preflight results for 24 hours, invalidating on runtime/model/path/version/SkillHub changes.
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

Preflight uses `testskills/exec-fixture-minimal` or an equivalent small built-in fixture to prove:

- the runtime can start in SkillHub's workspace mode
- skill instructions are visible to the agent
- the agent can invoke the entrypoint with a relative path from the working directory
- tool call evidence is captured
- stdout/result text can be parsed
- `actual_output` matches the fixture expectation
- failure reasons are specific if any step fails

Preflight output includes:

- `status`: `passed`, `failed`, `blocked`, `expired`, `missing`
- `runtime_id`, `model_id`, `cli_path`, `cli_version`, `skillhub_version`, `runtime_fingerprint`
- `checked_at`, `expires_at`
- `failure_reason`, `failure_message_zh`, `manual_hint`
- evidence summary: command observed, completion event observed, artifact/output observed

Cache invalidation occurs when any fingerprint input changes: runtime id, model id, resolved CLI path, CLI version, runtime definition fingerprint, or SkillHub version. Default TTL is 24 hours.

### Unified AgentEvent

Each adapter maps raw CLI output to a common event stream before SkillHub builds `ParsedStream` or `ExecResult`.

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

The generic `stream_parser.py` should become a consumer of normalized `AgentEvent`, not the place where all raw CLI dialects accumulate.

### Skill Injection

SkillHub supports three injection strategies:

1. **Native skill loading**: for runtimes that read a known local skill directory. Use when reliable for a runtime/version.
2. **File-placed workflow**: write project-local instruction files in the per-case workspace when a runtime supports workspace instructions.
3. **Prompt injection**: include `SKILL.md` and selected references in the composed harness prompt. This is the universal fallback.

The runtime definition declares preferred strategies and fallbacks. The injection layer is responsible for prompt-size checks and for staging only the relevant files. Script-entrypoint skills still execute in an isolated per-case workspace.

### Execution Flow

Formal local execution becomes:

1. Resolve selected runtime/model from preferences.
2. Verify preflight cache for the selected runtime/model/fingerprint.
3. If not passed, block before `case_executing` and surface `LOCAL_RUNTIME_PREFLIGHT_REQUIRED` or a specific readiness reason.
4. Build per-case workspace.
5. Inject skill instructions using the runtime's strategy.
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

### D4: Preflight cache is allowed but fingerprinted

Preflight is cached for 24 hours. Cache invalidates if agent/model/path/version/runtime fingerprint/SkillHub version changes.

### D5: Switching is explicit

The system never automatically switches runtimes after failure. The UI may offer one-click switch/retry to another preflight-passed runtime.

### D6: Scoring remains unchanged

Runtime platform changes stop at `ExecResult`. Existing judge, aggregation, R1-R8, thresholds, expert review, and report semantics stay intact.

## Risks / Trade-offs

- **Risk: Larger change surface.** Runtime registry, API, UI, tests, and execution source all change. Mitigation: phase implementation by compatibility layers and keep `ExecResult` as the engine boundary.
- **Risk: Preflight blocks users who just want to run.** Mitigation: show specific fix hints and allow explicit switch to any preflight-passed runtime.
- **Risk: Real CLI behavior varies by version.** Mitigation: store real stream fixtures and include CLI version in preflight fingerprints.
- **Risk: Native skill loading differs by agent/version.** Mitigation: every runtime must support prompt injection fallback.
- **Risk: Runtime platform could become broader than needed.** Mitigation: v1 excludes cloud fallback, automatic installation, artifact preview, and multi-agent comparison.

## Migration Plan

1. Add runtime contract types and adapt existing `AgentDef` data into the new shape without changing behavior.
2. Add unified `AgentEvent` types and map current Cursor/Trae/Codex/Claude/Antigravity parsers to them.
3. Build `ExecResult` from normalized events while preserving current report fields.
4. Add preflight runner and cache, initially using `exec-fixture-minimal`.
5. Gate formal local evaluation on valid preflight.
6. Expand scan/test API response to include readiness, preflight, model, auth, and failure taxonomy.
7. Update UI runtime cards and explicit switch/retry controls.
8. Add real stream fixture tests and opt-in live runtime E2E tests.
9. Update runbook and sprint docs.

## Open Questions

- None blocking. Product decisions resolved before proposal:
  - v1 includes Codex, Cursor Agent, Trae, Claude, Antigravity.
  - preflight is mandatory.
  - preflight is cached for 24 hours with fingerprint invalidation.
  - runtime switching is explicit only.
  - scoring remains unchanged.

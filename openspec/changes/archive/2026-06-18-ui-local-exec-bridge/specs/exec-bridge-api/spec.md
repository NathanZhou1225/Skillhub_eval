# Delta Spec: exec-bridge-api

Expose local agent discovery, session preferences, consent, and connection test over HTTP so the eval UI can configure W8 execution without editing `.env`.

## ADDED Requirements

### Requirement: Agent scan endpoint

The system SHALL provide `GET /api/exec/agents/scan` returning detected local CLI agents for claude, codex, and cursor-agent using the same adapter registry as `LocalAgentSource`.

#### Scenario: Scan lists PATH-detected agents

- **WHEN** client calls `GET /api/exec/agents/scan`
- **THEN** response includes `agents[]` with `id`, `label`, `detected` (boolean), and `scanned_at` ISO timestamp
- **AND** `detected=true` iff `shutil.which` finds the agent binary

#### Scenario: Scan includes optional auth hint for cursor-agent

- **WHEN** cursor-agent is on PATH
- **THEN** response MAY include `auth_status` of `unknown`, `ok`, or `fail` from a best-effort status probe
- **AND** scan MUST NOT spawn a full skill harness run

### Requirement: Global execution preferences

The system SHALL provide `GET /api/exec/preferences` and `PUT /api/exec/preferences` for machine-wide `exec_source` and `exec_agent` persisted in SQLite (single global row).

#### Scenario: Default preferences favor local execution

- **WHEN** no persisted preferences exist
- **THEN** `GET /api/exec/preferences` returns `exec_source=local` and `exec_agent` from env default or first detected agent

#### Scenario: PUT updates preferences immediately

- **WHEN** client sends `PUT /api/exec/preferences` with `{ "exec_source": "sample_io" }`
- **THEN** subsequent engine runs use sample_io without restart
- **AND** response echoes updated preferences including computed `ready` boolean
- **AND** preferences survive server process restart

#### Scenario: Ready flag semantics

- **WHEN** `exec_source=local` and selected agent is detected and consent is granted
- **THEN** `ready=true`
- **WHEN** `exec_source=sample_io`
- **THEN** `ready=true` regardless of CLI detection

### Requirement: Consent grant with persistence

The system SHALL provide `POST /api/exec/consent` to grant execution consent and persist it in global preferences.

#### Scenario: Consent enables local spawn

- **WHEN** client posts `POST /api/exec/consent`
- **THEN** consent is granted via existing `grant_exec_consent` mechanism
- **AND** `GET /api/exec/preferences` returns `consent_granted=true`

#### Scenario: Consent survives restart

- **WHEN** server process restarts after consent was granted via API
- **THEN** persisted preferences still report `consent_granted=true`

### Requirement: Agent connection test

The system SHALL provide `POST /api/exec/agents/{id}/test` to run a short smoke invocation of the named agent.

#### Scenario: Successful test

- **WHEN** agent `{id}` is detected and test is invoked
- **THEN** system spawns agent with minimal prompt and ≤5s timeout
- **AND** returns `{ "ok": true, "message": "..." }` on successful stream completion

#### Scenario: Failed test

- **WHEN** agent is not detected or spawn fails
- **THEN** returns `{ "ok": false, "message": "..." }` with HTTP 200 (UI displays failure inline)

#### Scenario: Test without prior consent

- **WHEN** consent has not been granted and test is invoked for a detected agent
- **THEN** test MAY still run as a connectivity smoke check
- **AND** consent state is unchanged

### Requirement: Preferences override environment defaults

The evaluation engine SHALL read persisted global preferences before `settings.exec_source` and `settings.exec_agent` when resolving execution routing.

#### Scenario: UI preference wins over env

- **WHEN** persisted `exec_source=local` and env `EXEC_SOURCE=sample_io`
- **THEN** `RoutingExecutionSource` uses local for evaluation runs

#### Scenario: Env fallback when no persisted row

- **WHEN** preferences store has no row yet
- **THEN** behavior matches pre-UI W8 env defaults until first PUT

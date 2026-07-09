"""Transport dispatch by AgentDef.stream_format.

stream-json → existing LocalAgentRunner. acp-json-rpc → future extension point.
"""

from __future__ import annotations

from skillhub_eval.core.schemas.report import RunOutcome
from skillhub_eval.execution.agent_registry import AgentDef
from skillhub_eval.execution.runner import AgentAdapter, LocalAgentRunner


def run_via_transport(
    adapter: AgentAdapter,
    agent: AgentDef,
    prompt: str,
    *,
    cwd: str,
    timeout_s: float,
    hardened: bool,
    runner: LocalAgentRunner | None = None,
    abort_check=None,
) -> RunOutcome:
    fmt = getattr(agent, "stream_format", "stream-json")
    if fmt == "stream-json":
        runner = runner or LocalAgentRunner()
        return runner.run(
            adapter,
            prompt,
            cwd=cwd,
            timeout_s=timeout_s,
            hardened=hardened,
            abort_check=abort_check,
        )
    if fmt == "acp-json-rpc":
        raise NotImplementedError(
            f"stream_format 'acp-json-rpc' not implemented for {agent.agent_id}; "
            "this is a documented extension point (see design G2)."
        )
    raise ValueError(f"unknown stream_format: {fmt}")

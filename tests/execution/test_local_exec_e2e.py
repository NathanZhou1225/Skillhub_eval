"""Real-CLI end-to-end smoke (opt-in).

Skipped unless RUN_LOCAL_AGENT=1, because it spawns a real, authenticated local
CLI agent (network + account cost). Used to verify the stream-json path end to
end for codex and trae on a real machine.
"""

import os

import pytest

from skillhub_eval.execution.agent_registry import resolve_adapter
from skillhub_eval.execution.runner import LocalAgentRunner

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LOCAL_AGENT") != "1",
    reason="requires local CLI (set RUN_LOCAL_AGENT=1)",
)


@pytest.mark.parametrize("agent_id", ["codex", "trae"])
def test_real_agent_runs(agent_id, tmp_path):
    adapter = resolve_adapter(agent_id)
    assert adapter and adapter.detect()
    outcome = LocalAgentRunner().run(
        adapter,
        "Reply with the single word OK.",
        cwd=str(tmp_path),
        timeout_s=120,
    )
    assert outcome.parsed_stream is not None

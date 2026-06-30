import pytest
from unittest.mock import MagicMock

from skillhub_eval.core.schemas.report import ParsedStream, RunOutcome
from skillhub_eval.execution.agent_registry import get_agent_def
from skillhub_eval.execution.transport import base


def test_dispatch_stream_json_calls_runner():
    runner = MagicMock()
    runner.run.return_value = RunOutcome(exit_code=0, parsed_stream=ParsedStream(final_text="x", is_complete=True))
    adapter = MagicMock(agent_id="trae")
    outcome = base.run_via_transport(
        adapter, get_agent_def("trae"), "p", cwd="/tmp",
        timeout_s=5, hardened=False, runner=runner,
    )
    assert outcome.parsed_stream.final_text == "x"
    runner.run.assert_called_once()


def test_dispatch_acp_is_extension_point():
    adapter = MagicMock(agent_id="x")
    fake_def = get_agent_def("trae").__class__(
        agent_id="x", label="X", adapter_factory=None, fallback_models=(),
        stream_format="acp-json-rpc",
    )
    with pytest.raises(NotImplementedError):
        base.run_via_transport(adapter, fake_def, "p", cwd="/tmp", timeout_s=5,
                               hardened=False, runner=MagicMock())

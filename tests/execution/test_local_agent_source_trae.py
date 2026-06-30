from unittest.mock import patch

from skillhub_eval.core.schemas.report import ParsedStream, RunOutcome
from skillhub_eval.execution.local_agent_source import LocalAgentSource


def test_trae_case_runs_via_transport(tmp_path):
    bundle = {"skill_id": "demo", "has_scripts": False}
    case = {"id": "happy_001", "type": "happy_path", "risk_level": "low"}
    outcome = RunOutcome(exit_code=0, parsed_stream=ParsedStream(
        final_text='{"ok": true}', is_complete=True, usage={"total_tokens": 5}))

    with patch("skillhub_eval.execution.local_agent_source.has_exec_consent", return_value=True), \
         patch("skillhub_eval.execution.preferences.get_exec_agent", return_value="trae"), \
         patch("skillhub_eval.execution.preferences.get_exec_model", return_value="default"), \
         patch("skillhub_eval.execution.adapters.trae.TraeAdapter.detect", return_value=True), \
         patch("skillhub_eval.execution.local_agent_source.run_via_transport", return_value=outcome) as rv:
        src = LocalAgentSource(timeout_s=5)
        result = src.get_actual_output(str(tmp_path), "happy_001", case=case, bundle=bundle)

    assert rv.called
    assert result.source == "local_agent" and result.status == "ok"
    assert result.usage == {"total_tokens": 5}
    assert result.agent_id == "trae"

from skillhub_eval.execution.evidence import verify_entrypoint_evidence


def test_verify_entrypoint_in_tool_stdout():
    tools = [{"stdout": "running scripts/run.py\nok", "exit_code": 0}]
    assert verify_entrypoint_evidence(tools, "scripts/run.py") is True


def test_verify_entrypoint_in_command_field():
    tools = [{"command": "bash scripts/run_diagnosis_pipeline.sh", "exit_code": 0}]
    assert verify_entrypoint_evidence(tools, "scripts/run_diagnosis_pipeline.sh") is True


def test_verify_entrypoint_missing():
    tools = [{"stdout": "only render_html.py", "exit_code": 0}]
    assert verify_entrypoint_evidence(tools, "scripts/run.py") is False


def test_verify_entrypoint_empty_tools():
    assert verify_entrypoint_evidence([], "scripts/run.py") is False

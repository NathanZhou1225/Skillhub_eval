from skillhub_eval.execution.failure_taxonomy import (
    runtime_failure_code,
    runtime_failure_label_zh,
)


def test_runtime_failure_code_maps_legacy_exec_reasons():
    assert runtime_failure_code("agent_unavailable") == "LOCAL_RUNTIME_CLI_UNAVAILABLE"
    assert runtime_failure_code("run_incomplete") == "LOCAL_RUNTIME_RUN_INCOMPLETE"
    assert runtime_failure_code("missing_entrypoint_evidence") == "LOCAL_RUNTIME_MISSING_ENTRYPOINT_EVIDENCE"


def test_runtime_failure_code_maps_preflight_reasons():
    assert runtime_failure_code("runtime_auth_missing") == "LOCAL_RUNTIME_AUTH_MISSING"
    assert runtime_failure_code("runtime_safe_preflight_required") == "LOCAL_RUNTIME_SAFE_PREFLIGHT_REQUIRED"
    assert runtime_failure_code("runtime_parser_missing") == "LOCAL_RUNTIME_PARSER_MISSING"
    assert runtime_failure_code("runtime_tool_failures_exceeded") == "LOCAL_RUNTIME_TOOL_FAILURES_EXCEEDED"
    assert runtime_failure_code("runtime_preflight_tool_budget_exceeded") == "LOCAL_RUNTIME_PREFLIGHT_TOOL_BUDGET_EXCEEDED"


def test_runtime_failure_label_accepts_reason_or_code():
    assert "入口脚本" in runtime_failure_label_zh("missing_entrypoint_evidence")
    assert "入口脚本" in runtime_failure_label_zh("LOCAL_RUNTIME_MISSING_ENTRYPOINT_EVIDENCE")
    assert runtime_failure_code("new_future_reason") == "LOCAL_RUNTIME_UNKNOWN"

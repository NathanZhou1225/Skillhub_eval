from skillhub_eval.execution.diagnostics import DiagnosisResult, check_writable


def test_diagnosis_result_is_a_frozen_dataclass():
    result = DiagnosisResult(ok=True, reason_code=None, message_zh="正常")
    assert result.ok is True
    assert result.manual_hint is None


def test_check_writable_true_for_writable_dir(tmp_path):
    assert check_writable(tmp_path) is True
    assert list(tmp_path.iterdir()) == []


def test_check_writable_false_for_missing_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert check_writable(missing) is False

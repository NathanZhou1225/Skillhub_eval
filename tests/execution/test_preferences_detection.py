from unittest.mock import patch

from skillhub_eval.execution import preferences
from skillhub_eval.execution.detection import DetectionResult


def test_compute_ready_uses_detection_ok():
    with patch.object(preferences, "_is_agent_detected", return_value=True):
        ready, reason = preferences.compute_ready("local", "codex", True)
    assert ready is True and reason is None


def test_is_agent_detected_routes_through_detection():
    with patch("skillhub_eval.execution.detection.detect_agent",
               return_value=DetectionResult("codex", True, "/bin/codex", "ok")) as d:
        assert preferences._is_agent_detected("codex") is True
        d.assert_called_once()


def test_is_agent_detected_false_when_unknown_agent():
    with patch("skillhub_eval.execution.agent_registry.get_agent_def", return_value=None):
        assert preferences._is_agent_detected("nope") is False

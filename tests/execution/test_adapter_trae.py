from unittest.mock import patch

from skillhub_eval.execution.adapters.trae import TraeAdapter


def test_build_args_stream_json():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model=None).build_args(cwd="/tmp")
    assert args[0] == "trae-cli"
    assert "-p" in args or "--print" in args
    assert "--output-format" in args and "stream-json" in args
    assert "--yolo" in args
    assert "acp" not in args  # G1: no longer ACP


def test_build_args_includes_model():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model="GLM-5.2").build_args(cwd="/tmp")
    assert "--model" in args and "GLM-5.2" in args


def test_parse_stream_reuses_generic_parser():
    a = TraeAdapter()
    parsed = a.parse_stream(['{"type":"result","result":"ok"}'])
    assert parsed.is_complete is True

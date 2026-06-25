from unittest.mock import patch

from skillhub_eval.execution.adapters.trae import TraeAdapter


def test_trae_build_args_default_model():
    args = TraeAdapter().build_args(cwd="/ws")

    assert args[0] == "traecli"
    assert "acp" in args
    assert "serve" in args
    assert "--yolo" in args
    assert "--model" not in args


def test_trae_build_args_with_model():
    args = TraeAdapter(model="gpt-5").build_args(cwd="/ws")

    assert "--model" in args
    assert args[args.index("--model") + 1] == "gpt-5"


@patch("skillhub_eval.execution.adapters.trae.find_cli_binary", return_value="/bin/traecli")
def test_trae_detect(mock_find):
    adapter = TraeAdapter()

    assert adapter.detect() is True
    assert adapter.resolved_bin() == "/bin/traecli"


def test_trae_resolved_bin_falls_back_to_trae_binary():
    def fake_find(name: str):
        return "/bin/trae" if name == "trae" else None

    with patch("skillhub_eval.execution.adapters.trae.find_cli_binary", side_effect=fake_find):
        adapter = TraeAdapter()
        assert adapter.detect() is True
        assert adapter.resolved_bin() == "/bin/trae"

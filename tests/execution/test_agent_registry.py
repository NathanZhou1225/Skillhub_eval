from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    fallback_models_for,
    get_agent_def,
    get_agent_catalog,
    resolve_adapter,
)


def test_catalog_order_and_hardened_flags():
    catalog = get_agent_catalog()

    assert [agent.agent_id for agent in catalog] == [
        "claude",
        "codex",
        "cursor-agent",
        "trae",
        "antigravity",
    ]
    assert {
        agent.agent_id: agent.supports_hardened_redline for agent in catalog
    } == {
        "claude": False,
        "codex": True,
        "cursor-agent": False,
        "trae": False,
        "antigravity": False,
    }


def test_fallback_model_lists_start_with_default_and_have_labels():
    for agent in get_agent_catalog():
        models = fallback_models_for(agent.agent_id)
        assert models
        assert models[0].model_id == DEFAULT_MODEL_ID
        assert all(model.label for model in models)


def test_registry_exposes_future_api_compat_properties():
    agent = get_agent_def("codex")
    models = fallback_models_for("codex")

    assert agent is not None
    assert agent.id == "codex"
    assert agent.bin == "codex"
    assert models[0].id == DEFAULT_MODEL_ID
    assert models[0].model == DEFAULT_MODEL_ID


def test_registry_exposes_agent_binary_names():
    trae = get_agent_def("trae")
    antigravity = get_agent_def("antigravity")
    cursor = get_agent_def("cursor_agent")

    assert trae is not None
    assert trae.bin == "trae-cli"
    assert trae.binary_names[0] == "trae-cli"
    assert "traecli" in trae.binary_names
    assert antigravity is not None
    assert antigravity.bin == "agy"
    assert cursor is not None
    assert cursor.id == "cursor-agent"
    assert cursor.bin == "cursor-agent"
    assert cursor.binary_names == ("cursor-agent",)


def test_resolve_adapter_passes_non_default_model():
    adapter = resolve_adapter("codex", model="gpt-5-codex")

    assert adapter is not None
    assert adapter.agent_id == "codex"
    assert adapter.model == "gpt-5-codex"


def test_resolve_adapter_converts_default_model_to_none():
    adapter = resolve_adapter("claude", model=DEFAULT_MODEL_ID)

    assert adapter is not None
    assert adapter.agent_id == "claude"
    assert adapter.model is None


def test_resolve_adapter_converts_empty_model_to_none():
    adapter = resolve_adapter("codex", model="")

    assert adapter is not None
    assert adapter.agent_id == "codex"
    assert adapter.model is None


def test_resolve_adapter_accepts_cursor_agent_alias():
    adapter = resolve_adapter("cursor_agent")

    assert adapter is not None
    assert adapter.agent_id == "cursor-agent"


def test_resolve_adapter_unknown_returns_none():
    assert resolve_adapter("unknown") is None


def test_defs_declare_framework_fields():
    codex = get_agent_def("codex")
    assert codex.stream_format == "stream-json"
    assert any(".codex" in d for d in codex.config_dirs)
    assert any("Codex" in g for g in codex.install_dir_globs)

    trae = get_agent_def("trae")
    assert trae.stream_format == "stream-json"
    assert trae.primary_bin == "trae-cli"
    assert "traecli" in trae.binary_aliases and "ta" in trae.binary_aliases
    assert trae.model_probe == ("models",)
    assert any("trae-cli" in g for g in trae.install_dir_globs)

    cursor = get_agent_def("cursor-agent")
    assert cursor.model_probe == ("--list-models",)

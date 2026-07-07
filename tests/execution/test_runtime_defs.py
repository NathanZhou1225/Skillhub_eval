from dataclasses import asdict, fields

from skillhub_eval.execution.agent_registry import get_agent_catalog
from skillhub_eval.execution.runtime_defs import (
    PromptTransport,
    RuntimeDef,
    SkillInjectionStrategy,
    StreamFormat,
    get_runtime_catalog,
    get_runtime_def,
)
from skillhub_eval.execution.preferences import set_preferences
from skillhub_eval.persistence.sqlite import SqliteRepository


def test_builtin_runtime_catalog_contains_five_productized_runtimes():
    ids = {rt.runtime_id for rt in get_runtime_catalog()}

    assert {"codex", "cursor-agent", "trae", "claude", "antigravity"} <= ids


def test_runtime_def_has_required_contract_fields():
    trae = get_runtime_def("trae")

    assert trae is not None
    assert trae.label == "Trae"
    assert trae.binary.primary
    assert trae.launch.prompt_transport in {
        PromptTransport.STDIN,
        PromptTransport.ARGV,
        PromptTransport.PROMPT_FILE,
    }
    assert SkillInjectionStrategy.PROMPT in trae.skill_injection.fallbacks
    assert trae.preflight.fixture_id == "exec-fixture-minimal"


def test_runtime_alias_lookup_preserves_existing_agent_ids():
    assert get_runtime_def("cursor_agent").runtime_id == "cursor-agent"
    assert get_runtime_def("ta").runtime_id == "trae"
    assert get_runtime_def("traecli").runtime_id == "trae"
    assert get_runtime_def("trae-agent").runtime_id == "trae"


def test_runtime_lookup_resolves_primary_binary_names():
    assert get_runtime_def("trae-cli").runtime_id == "trae"
    assert get_runtime_def("agy").runtime_id == "antigravity"


def test_runtime_catalog_has_unique_ids():
    ids = [rt.runtime_id for rt in get_runtime_catalog()]

    assert len(ids) == len(set(ids))


def test_runtime_catalog_matches_existing_agent_registry_contract():
    runtimes = {runtime.runtime_id: runtime for runtime in get_runtime_catalog()}
    agents = {agent.agent_id: agent for agent in get_agent_catalog()}

    assert set(runtimes) == set(agents)
    for runtime_id, agent in agents.items():
        runtime = runtimes[runtime_id]
        expected_transport = (
            PromptTransport.STDIN if agent.prompt_via_stdin else PromptTransport.ARGV
        )

        assert runtime.label == agent.label
        assert runtime.binary.primary == agent.bin
        assert runtime.binary.aliases == agent.binary_aliases
        assert runtime.binary.install_dir_globs == agent.install_dir_globs
        assert runtime.binary.version_args == agent.version_args
        assert runtime.config_dirs == agent.config_dirs
        assert runtime.aliases == agent.aliases
        assert runtime.models.fallback_models == agent.fallback_models
        assert runtime.models.model_probe == agent.model_probe
        assert runtime.models.fallback_model_probes == agent.fallback_model_probes
        assert runtime.launch.stream_format == StreamFormat(agent.stream_format)
        assert runtime.launch.prompt_transport == expected_transport
        assert (
            runtime.launch.supports_hardened_redline
            == agent.supports_hardened_redline
        )


def test_runtime_catalog_declares_cross_runtime_semantics():
    codex = get_runtime_def("codex")
    claude = get_runtime_def("claude")
    cursor = get_runtime_def("cursor-agent")
    trae = get_runtime_def("trae")

    assert trae.launch.prompt_transport == PromptTransport.ARGV
    assert codex.skill_injection.preferred == SkillInjectionStrategy.NATIVE
    assert claude.skill_injection.preferred == SkillInjectionStrategy.NATIVE
    assert cursor.skill_injection.preferred == SkillInjectionStrategy.FILE_PLACED
    assert codex.launch.supports_hardened_redline is True
    assert trae.models.model_probe == ("models",)
    assert cursor.models.model_probe == ("models",)
    assert ("--list-models",) in cursor.models.fallback_model_probes


def test_runtime_def_stores_project_contract_not_machine_state(monkeypatch, tmp_path):
    forbidden_field_names = {
        "resolved_cli_path",
        "cli_path",
        "selected_runtime",
        "selected_model",
        "auth_status",
        "readiness_status",
        "readiness_probe_result",
        "preflight_cache",
        "preflight_result",
        "switch_preference",
        "one_click_switch_preference",
    }
    runtime_field_names = {field.name for field in fields(RuntimeDef)}

    assert runtime_field_names.isdisjoint(forbidden_field_names)

    catalog_before = asdict(get_runtime_def("codex"))
    db_path = str(tmp_path / "prefs.db")
    SqliteRepository(db_path).init_db()
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._is_agent_detected",
        lambda agent_id: True,
    )

    simulated_machine_state = {
        "resolved_cli_path": r"C:\Tools\codex.exe",
        "selected_runtime": "cursor-agent",
        "selected_model": "gpt-5",
        "auth_status": "ok",
        "readiness_probe_result": {"status": "ok"},
        "preflight_cache": {"fixture_id": "exec-fixture-minimal", "passed": True},
        "one_click_switch_preference": "trae",
    }
    assert simulated_machine_state
    set_preferences(
        db_path=db_path,
        exec_source="local",
        exec_agent=simulated_machine_state["selected_runtime"],
        exec_model=simulated_machine_state["selected_model"],
        consent_granted=True,
    )

    catalog_after = asdict(get_runtime_def("codex"))

    assert catalog_after == catalog_before
    serialized = repr(get_runtime_catalog())
    for value in (
        simulated_machine_state["resolved_cli_path"],
        simulated_machine_state["readiness_probe_result"],
        simulated_machine_state["preflight_cache"],
    ):
        assert str(value) not in serialized

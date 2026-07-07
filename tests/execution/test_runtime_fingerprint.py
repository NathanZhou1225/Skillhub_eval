from skillhub_eval.execution.runtime_defs import get_runtime_def
from skillhub_eval.execution.runtime_fingerprint import (
    runtime_fingerprint,
    skill_fingerprint,
)


def test_runtime_fingerprint_is_stable_for_same_inputs():
    runtime = get_runtime_def("cursor-agent")

    first = runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="C:/cli/cursor-agent.exe",
        cli_version="cursor-agent 1.2.3",
        skillhub_version="0.1-test",
    )
    second = runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="C:/cli/cursor-agent.exe",
        cli_version="cursor-agent 1.2.3",
        skillhub_version="0.1-test",
    )

    assert first == second


def test_runtime_fingerprint_changes_when_runtime_inputs_change():
    runtime = get_runtime_def("cursor-agent")

    baseline = runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="p",
        cli_version="v",
        skillhub_version="s",
    )

    assert baseline != runtime_fingerprint(
        runtime,
        model_id="default",
        cli_path="p",
        cli_version="v",
        skillhub_version="s",
    )
    assert baseline != runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="other",
        cli_version="v",
        skillhub_version="s",
    )
    assert baseline != runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="p",
        cli_version="other",
        skillhub_version="s",
    )
    assert baseline != runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="p",
        cli_version="v",
        skillhub_version="other",
    )
    assert baseline != runtime_fingerprint(
        get_runtime_def("trae"),
        model_id="gpt-5",
        cli_path="p",
        cli_version="v",
        skillhub_version="s",
    )


def test_skill_fingerprint_changes_when_skill_content_changes(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("v1", encoding="utf-8")
    first = skill_fingerprint(skill_dir)

    skill_md.write_text("v2", encoding="utf-8")
    second = skill_fingerprint(skill_dir)

    assert first != second


def test_skill_fingerprint_ignores_cache_and_git_directories(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("stable", encoding="utf-8")
    first = skill_fingerprint(skill_dir)

    for dirname in (".git", "__pycache__", ".pytest_cache"):
        ignored = skill_dir / dirname
        ignored.mkdir()
        (ignored / "volatile.txt").write_text(dirname, encoding="utf-8")

    assert skill_fingerprint(skill_dir) == first


def test_skill_fingerprint_uses_relative_paths_deterministically(tmp_path):
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    for root in (first_dir, second_dir):
        (root / "nested").mkdir(parents=True)
        (root / "SKILL.md").write_bytes(b"\xe6\x8a\x80\xe8\x83\xbd")
        (root / "nested" / "case.yaml").write_text("id: c1\n", encoding="utf-8")

    assert skill_fingerprint(first_dir) == skill_fingerprint(second_dir)

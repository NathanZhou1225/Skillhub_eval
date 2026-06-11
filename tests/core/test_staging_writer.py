import json
from pathlib import Path

import pytest
import yaml

from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.providers.base import BaseLLMProvider


class _NoopProvider(BaseLLMProvider):
    async def judge(self, prompt: str) -> dict:  # pragma: no cover
        return {}


class _DummyBackgroundTasks:
    def __init__(self) -> None:
        self.tasks: list[tuple] = []

    def add_task(self, func, *args, **kwargs) -> None:  # noqa: ANN001
        self.tasks.append((func, args, kwargs))


def _make_repo(tmp_path: Path) -> SqliteRepository:
    repo = SqliteRepository(str(tmp_path / "staging_writer.db"))
    repo.init_db()
    return repo


def _make_bundle(
    root: Path,
    *,
    with_frontmatter: bool = True,
    n_cases: int = 3,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if with_frontmatter:
        (root / "SKILL.md").write_text(
            "---\nname: demo\nid: demo.skill\nrisk_level: low\ndescription: demo\n---\n# Body\nunchanged line\n",
            encoding="utf-8",
        )
    else:
        (root / "SKILL.md").write_text(
            "# No frontmatter\nplain body\n",
            encoding="utf-8",
        )
    eval_cases_dir = root / "eval_cases"
    eval_cases_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n_cases):
        (eval_cases_dir / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: intent {i}\n",
            encoding="utf-8",
        )
    (root / "sample_io").mkdir(parents=True, exist_ok=True)
    return root


def test_apply_patch_updates_frontmatter_only_and_keeps_body(tmp_path: Path):
    from skillhub_eval.core.staging_writer import StagingWriter

    repo = _make_repo(tmp_path)
    writer = StagingWriter(repo)
    staging = _make_bundle(tmp_path / "bundle")

    before = (staging / "SKILL.md").read_text(encoding="utf-8")
    before_body = before.split("---", 2)[2]

    result = writer.apply_patch(
        staging,
        {"skill_md_updates": {"category": "fin-research/quant-signal"}},
    )

    after = (staging / "SKILL.md").read_text(encoding="utf-8")
    after_body = after.split("---", 2)[2]
    fm = yaml.safe_load(after.split("---", 2)[1])

    assert result.hash_changed is True
    assert "SKILL.md" in result.files_written
    assert fm["category"] == "fin-research/quant-signal"
    assert after_body == before_body


def test_apply_patch_without_frontmatter_is_noop(tmp_path: Path):
    from skillhub_eval.core.staging_writer import StagingWriter

    repo = _make_repo(tmp_path)
    writer = StagingWriter(repo)
    staging = _make_bundle(tmp_path / "bundle_no_fm", with_frontmatter=False)

    before = (staging / "SKILL.md").read_text(encoding="utf-8")
    result = writer.apply_patch(
        staging,
        {"skill_md_updates": {"category": "fin-research/quant-signal"}},
    )
    after = (staging / "SKILL.md").read_text(encoding="utf-8")

    assert result.hash_changed is False
    assert result.files_written == []
    assert after == before


def test_compute_next_run_mode_routes_a_b_c(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import skillhub_eval.core.staging_writer as staging_writer_module
    from skillhub_eval.core.staging_writer import StagingWriter

    repo = _make_repo(tmp_path)
    writer = StagingWriter(repo)

    # Route A: case gate fails -> degraded + minimal
    staging_a = _make_bundle(tmp_path / "route_a", n_cases=1)
    mode_a, state_a = writer.compute_next_run_mode(
        staging_a,
        {"auto_confirmed": 0},
    )
    assert mode_a == EvaluationMode.degraded
    assert state_a == BundleState.minimal

    # Route B: gate passes but required gaps exist -> degraded + draft_enriched
    staging_b = _make_bundle(tmp_path / "route_b", n_cases=3)

    def _fake_scan_gaps(_bundle: dict, _bundle_state: BundleState) -> dict:
        return {"gaps": [{"severity": "required", "field_path": "x"}]}

    monkeypatch.setattr(staging_writer_module, "scan_gaps", _fake_scan_gaps)
    mode_b, state_b = writer.compute_next_run_mode(
        staging_b,
        {"auto_confirmed": 0},
    )
    assert mode_b == EvaluationMode.degraded
    assert state_b == BundleState.draft_enriched

    # Route C: gate passes + no required gaps + auto_confirmed -> capability_full + confirmed
    monkeypatch.setattr(
        staging_writer_module,
        "scan_gaps",
        lambda _bundle, _bundle_state: {"gaps": []},
    )
    mode_c, state_c = writer.compute_next_run_mode(
        staging_b,
        {"auto_confirmed": 1},
    )
    assert mode_c == EvaluationMode.capability_full
    assert state_c == BundleState.confirmed


@pytest.mark.asyncio
async def test_trigger_next_run_quota_full_freezes_and_returns_none(tmp_path: Path):
    from skillhub_eval.core.staging_writer import StagingWriter

    repo = _make_repo(tmp_path)
    staging = _make_bundle(tmp_path / "bundle")

    conv_id = repo.create_conversation(skill_id="demo.skill", source="upload")
    repo.set_conversation_auto_confirmed(conv_id, True)
    old_run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    for _ in range(5):
        repo.increment_auto_run_count(conv_id)

    writer = StagingWriter(repo)
    bg = _DummyBackgroundTasks()
    new_run_id = await writer.trigger_next_run(
        conv_id=conv_id,
        old_run_id=old_run_id,
        staging_path=staging,
        skill_id="demo.skill",
        ds_provider=_NoopProvider(),
        gemini_provider=_NoopProvider(),
        background_tasks=bg,
    )

    assert new_run_id is None
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "frozen"

    run = repo.get_run(old_run_id)
    assert run is not None
    assert run["status"] == "awaiting_human_review"
    assert run["human_review_required"] == 1
    trigger_codes = json.loads(run["human_review_trigger_codes"])
    assert "CONVERSATION_QUOTA_EXCEEDED" in trigger_codes

    msgs = repo.get_lui_messages(conv_id)
    assert any("最大自动修改次数" in m["content"] for m in msgs)
    assert bg.tasks == []


@pytest.mark.asyncio
async def test_trigger_next_run_degraded_does_not_increment_quota(tmp_path: Path):
    from skillhub_eval.core.staging_writer import StagingWriter

    repo = _make_repo(tmp_path)
    staging = _make_bundle(tmp_path / "bundle")

    conv_id = repo.create_conversation(skill_id="demo.skill", source="upload")
    old_run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )

    writer = StagingWriter(repo)
    bg = _DummyBackgroundTasks()
    new_run_id = await writer.trigger_next_run(
        conv_id=conv_id,
        old_run_id=old_run_id,
        staging_path=staging,
        skill_id="demo.skill",
        ds_provider=_NoopProvider(),
        gemini_provider=_NoopProvider(),
        background_tasks=bg,
    )

    assert new_run_id is not None
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["auto_run_count"] == 0


@pytest.mark.asyncio
async def test_trigger_next_run_creates_new_lineage_and_supersedes_old(tmp_path: Path):
    from skillhub_eval.core.staging_writer import StagingWriter

    repo = _make_repo(tmp_path)
    staging = _make_bundle(tmp_path / "bundle")

    conv_id = repo.create_conversation(skill_id="demo.skill", source="upload")
    repo.set_conversation_auto_confirmed(conv_id, True)
    old_run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )

    writer = StagingWriter(repo)
    bg = _DummyBackgroundTasks()
    new_run_id = await writer.trigger_next_run(
        conv_id=conv_id,
        old_run_id=old_run_id,
        staging_path=staging,
        skill_id="demo.skill",
        ds_provider=_NoopProvider(),
        gemini_provider=_NoopProvider(),
        background_tasks=bg,
    )

    assert new_run_id is not None

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["auto_run_count"] == 1
    assert conv["active_run_id"] == new_run_id

    old_run = repo.get_run(old_run_id)
    assert old_run is not None
    assert old_run["status"] == "superseded"
    assert old_run["superseded_by_run_id"] == new_run_id

    new_run = repo.get_run(new_run_id)
    assert new_run is not None
    assert new_run["parent_run_id"] == old_run_id
    assert len(bg.tasks) == 1

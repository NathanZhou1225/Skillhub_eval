import json
from pathlib import Path

from skillhub_eval.execution.workspace import PerRunWorkspace


def test_workspace_clone_isolates_runs(tmp_path):
    bundle = tmp_path / "skill"
    bundle.mkdir()
    (bundle / "SKILL.md").write_text("# x\n", encoding="utf-8")
    (bundle / "marker.txt").write_text("orig", encoding="utf-8")

    ws = PerRunWorkspace(retain=True)
    p1 = ws.acquire(str(bundle), "h01")
    p2 = ws.acquire(str(bundle), "h02")
    assert p1 != p2
    assert (p1 / "marker.txt").read_text(encoding="utf-8") == "orig"
    (p1 / "marker.txt").write_text("mutated", encoding="utf-8")
    assert (p2 / "marker.txt").read_text(encoding="utf-8") == "orig"
    ws.release(p1)
    ws.release(p2)


def test_workspace_release_cleans_when_not_retain(tmp_path):
    bundle = tmp_path / "skill"
    bundle.mkdir()
    (bundle / "a.json").write_text("{}", encoding="utf-8")
    ws = PerRunWorkspace(retain=False)
    run_dir = ws.acquire(str(bundle), "c01")
    assert run_dir.exists()
    ws.release(run_dir)
    assert not run_dir.exists()

"""Ingest bundle and eval_cases loading tests."""

from skillhub_eval.core.ingest import _load_cases, ingest_bundle


def test_load_cases_valid_yaml(tmp_path):
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    (ec / "c01.yaml").write_text(
        "id: c01\ntype: happy_path\nuser_intent: test intent\n",
        encoding="utf-8",
    )

    cases, malformed = _load_cases(ec)

    assert len(cases) == 1
    assert len(malformed) == 0
    assert cases[0]["id"] == "c01"
    assert cases[0]["type"] == "happy_path"
    assert cases[0]["user_intent"] == "test intent"
    assert cases[0]["_path"].endswith("c01.yaml")


def test_load_cases_parse_error_goes_to_malformed(tmp_path):
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    bad = ec / "broken.yaml"
    bad.write_text("{not: valid: yaml: [\n", encoding="utf-8")

    cases, malformed = _load_cases(ec)

    assert cases == []
    assert len(malformed) == 1
    assert malformed[0]["path"] == str(bad)
    assert malformed[0]["reason"].startswith("parse_error:")


def test_load_cases_missing_id_goes_to_malformed(tmp_path):
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    shell = ec / "empty_shell.yaml"
    shell.write_text("type: happy_path\nuser_intent: no id here\n", encoding="utf-8")

    cases, malformed = _load_cases(ec)

    assert cases == []
    assert len(malformed) == 1
    assert malformed[0]["path"] == str(shell)
    assert malformed[0]["reason"] == "missing_id"


def test_ingest_bundle_includes_malformed_cases(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: test-skill\nrisk_level: low\n---\n# Test\n",
        encoding="utf-8",
    )
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    (ec / "valid.yaml").write_text(
        "id: valid\ntype: happy_path\nuser_intent: ok\n",
        encoding="utf-8",
    )
    (ec / "broken.yaml").write_text("not yaml: [[[\n", encoding="utf-8")
    (ec / "no_id.yaml").write_text("type: edge_case\n", encoding="utf-8")

    bundle = ingest_bundle(str(tmp_path))

    assert bundle["n_cases"] == 1
    assert len(bundle["eval_cases"]) == 1
    assert bundle["eval_cases"][0]["id"] == "valid"
    assert len(bundle["malformed_cases"]) == 2
    reasons = {m["reason"] for m in bundle["malformed_cases"]}
    assert "missing_id" in reasons
    assert any(r.startswith("parse_error:") for r in reasons)

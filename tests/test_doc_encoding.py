"""Guard RECORD.md and .project_memory Markdown encoding (R-core)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_doc_encoding", ROOT / "scripts" / "check_doc_encoding.py"
)
assert _SPEC and _SPEC.loader
cde = importlib.util.module_from_spec(_SPEC)
sys.modules["check_doc_encoding"] = cde
_SPEC.loader.exec_module(cde)


GOOD_UTF8 = "# 总账文档\n\n## 任务目标\n\n正常中文内容。\n"
MOJIBAKE_UTF8 = "# RECORD 鈥?SkillHub\n\n> 鎬昏处鏂囨。：记录项目目标。\n"
ARROW_MOJIBAKE_UTF8 = "Pipeline 鈫? archive\n"
PRIVATE_USE_UTF8 = "正常\uE001\uE002\uE003\uE004\uE005\uE006前缀\n"


def test_good_text_passes():
    issues = cde.check_decoded_text(GOOD_UTF8)
    assert issues == []


def test_mojibake_substring_fails():
    issues = cde.check_decoded_text(MOJIBAKE_UTF8)
    codes = {i.code for i in issues}
    assert "mojibake_substring" in codes


def test_arrow_mojibake_substring_fails():
    issues = cde.check_decoded_text(ARROW_MOJIBAKE_UTF8)
    codes = {i.code for i in issues}
    assert "mojibake_substring" in codes


def test_default_targets_include_cursor_rules():
    targets = {p.relative_to(ROOT).as_posix() for p in cde.default_targets(ROOT)}
    assert ".cursor/rules/doc-encoding-utf8.mdc" in targets
    assert ".cursor/rules/integrated-ai-workflow.mdc" in targets


def test_record_anchor_required():
    issues = cde.check_decoded_text("## 任务目标\n", record_anchor=True)
    assert any(i.code == "record_anchor" for i in issues)


def test_utf8_bom_fails():
    raw = UTF8_BOM + GOOD_UTF8.encode("utf-8")
    issues = cde.check_bytes(raw)
    assert any(i.code == "utf8_bom" for i in issues)


def test_private_use_threshold():
    issues = cde.check_decoded_text(PRIVATE_USE_UTF8)
    assert any(i.code == "private_use_chars" for i in issues)


def test_repo_record_and_project_memory_pass():
    issues = cde.check_all(ROOT)
    assert issues == [], "\n".join(f"{i.path}: {i.message}" for i in issues)


@pytest.mark.parametrize(
    "text,expect_fail",
    [
        (GOOD_UTF8, False),
        (MOJIBAKE_UTF8, True),
    ],
)
def test_bytes_roundtrip(text: str, expect_fail: bool):
    issues = cde.check_bytes(text.encode("utf-8"))
    failed = any(i.code == "mojibake_substring" for i in issues)
    assert failed == expect_fail


UTF8_BOM = cde.UTF8_BOM

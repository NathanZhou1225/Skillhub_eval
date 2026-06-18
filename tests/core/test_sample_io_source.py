import json
from pathlib import Path

import pytest

from skillhub_eval.core.sample_io_source import SampleIoSource


@pytest.fixture
def bundle_with_sample_io(tmp_path: Path) -> str:
    root = tmp_path / "skill"
    (root / "sample_io").mkdir(parents=True)
    (root / "sample_io" / "h01.json").write_text(
        json.dumps({"message": "ok"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(root)


def test_sample_io_source_returns_exec_result(bundle_with_sample_io: str):
    src = SampleIoSource()
    result = src.get_actual_output(bundle_with_sample_io, "h01")
    assert result.actual_output == {"message": "ok"}
    assert result.source == "sample_io"
    assert result.level == "level_1"
    assert result.status == "ok"
    assert result.confidence == "high"


def test_sample_io_source_missing_case_returns_none_output(bundle_with_sample_io: str):
    src = SampleIoSource()
    result = src.get_actual_output(bundle_with_sample_io, "missing")
    assert result.actual_output is None
    assert result.source == "sample_io"
    assert result.status == "ok"

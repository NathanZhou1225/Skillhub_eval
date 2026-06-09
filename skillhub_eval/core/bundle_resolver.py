from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from skillhub_eval.settings import settings


@dataclass
class BundleRef:
    conversation_id: str
    source: str  # 'local_ref' | 'upload'
    source_path: Path | None
    staging_path: Path


class BundleNotReadyError(Exception):
    """staging 未就绪且无法从 source fallback 时抛出（upload 模式下的非法访问）。"""


class BundleResolver:
    def __init__(self, ref: BundleRef) -> None:
        self.ref = ref

    def ensure_staging(self) -> None:
        staging_dir = self.ref.staging_path
        if self.ref.source == "upload":
            staging_dir.mkdir(parents=True, exist_ok=True)
            return

        if staging_dir.exists():
            return

        tmp_dir = staging_dir.with_suffix(".tmp")
        try:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            shutil.copytree(self.ref.source_path, tmp_dir)
            tmp_dir.rename(staging_dir)
        except Exception:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            raise

    def get_file_content(self, relative_path: str) -> str:
        target = self.ref.staging_path / relative_path
        if target.exists():
            return target.read_text(encoding="utf-8")

        if self.ref.source_path is not None:
            src = self.ref.source_path / relative_path
            if src.exists():
                return src.read_text(encoding="utf-8")
            raise FileNotFoundError(relative_path)

        raise BundleNotReadyError(
            f"staging not ready and no source fallback for: {relative_path}"
        )

    def write_file_content(self, relative_path: str, content: str) -> None:
        self.ensure_staging()
        target = self.ref.staging_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def list_files(self, subdir: str = "") -> list[str]:
        base = self.ref.staging_path / subdir
        if not base.exists():
            return []
        return sorted(
            str(path.relative_to(self.ref.staging_path)).replace("\\", "/")
            for path in base.rglob("*")
            if path.is_file()
        )

    @classmethod
    def from_settings(
        cls,
        conversation_id: str,
        source: str,
        source_path: str | None = None,
    ) -> BundleResolver:
        if source == "local_ref" and not source_path:
            raise ValueError("local_ref requires source_path")
        ref = BundleRef(
            conversation_id=conversation_id,
            source=source,
            source_path=Path(source_path) if source_path else None,
            staging_path=Path(settings.staging_root) / conversation_id,
        )
        return cls(ref)

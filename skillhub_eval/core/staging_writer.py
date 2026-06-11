from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from skillhub_eval.core.gaps import scan_gaps
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.level0 import Level0Checker
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.providers.base import BaseLLMProvider

_TYPE_ABBR: dict[str, str] = {
    "happy_path": "hp",
    "edge": "ec",
    "refusal": "rf",
    "adversarial": "adv",
}


@dataclass
class WriterResult:
    files_written: list[str]
    hash_changed: bool


class StagingWriter:
    def __init__(self, repo: Repository):
        self.repo = repo

    def apply_patch(self, staging_path: Path, patch: dict) -> WriterResult:
        staging_path = Path(staging_path)
        before_hash = self._tree_hash(staging_path)
        files_written: list[str] = []

        updates = patch.get("skill_md_updates")
        if isinstance(updates, dict) and updates:
            if self._patch_skill_md(staging_path, updates):
                files_written.append("SKILL.md")

        cases = patch.get("eval_cases")
        if isinstance(cases, list) and cases:
            files_written.extend(self._write_cases(staging_path, cases))

        after_hash = self._tree_hash(staging_path)
        return WriterResult(
            files_written=files_written,
            hash_changed=before_hash != after_hash,
        )

    def compute_next_run_mode(
        self,
        staging_path: Path,
        conv: dict,
    ) -> tuple[EvaluationMode, BundleState]:
        bundle = ingest_bundle(str(staging_path))
        gate = Level0Checker().check_case_gate(bundle)
        if not gate.get("passed", False):
            return EvaluationMode.degraded, BundleState.minimal

        gaps = scan_gaps(bundle, BundleState.draft_enriched)
        required_gaps = [
            g for g in gaps.get("gaps", []) if g.get("severity") == "required"
        ]
        if required_gaps:
            return EvaluationMode.degraded, BundleState.draft_enriched

        if conv.get("auto_confirmed"):
            return EvaluationMode.capability_full, BundleState.confirmed
        return EvaluationMode.degraded, BundleState.draft_enriched

    async def trigger_next_run(
        self,
        conv_id: str,
        old_run_id: str | None,
        staging_path: Path,
        skill_id: str,
        ds_provider: BaseLLMProvider,
        gemini_provider: BaseLLMProvider,
        background_tasks: Any,
    ) -> str | None:
        conv = self.repo.get_conversation(conv_id) or {}
        eval_mode, bundle_state = self.compute_next_run_mode(staging_path, conv)

        if eval_mode == EvaluationMode.capability_full:
            auto_run_count = int(conv.get("auto_run_count", 0))
            max_auto_runs = int(conv.get("max_auto_runs", 5))
            if auto_run_count >= max_auto_runs:
                active_run_id = str(conv.get("active_run_id") or old_run_id)
                self._freeze_and_escalate(conv_id, active_run_id)
                return None
            self.repo.increment_auto_run_count(conv_id)
            conv = self.repo.get_conversation(conv_id) or conv

        new_run_id = self.repo.create_run(
            skill_id=skill_id,
            skill_bundle_path=str(staging_path),
            bundle_state=bundle_state.value,
            evaluation_mode=eval_mode.value,
            conversation_id=conv_id,
            parent_run_id=old_run_id,
        )
        if old_run_id:
            self.repo.supersede_run(old_run_id, new_run_id)

        from skillhub_eval.core.engine import EvaluationEngine

        engine = EvaluationEngine(
            repo=self.repo,
            ds_provider=ds_provider,
            wb_provider=gemini_provider,
        )
        background_tasks.add_task(
            engine.run_async,
            run_id=new_run_id,
            skill_bundle_path=str(staging_path),
            bundle_state=bundle_state,
            evaluation_mode=eval_mode,
        )
        return new_run_id

    def _freeze_and_escalate(self, conv_id: str, active_run_id: str) -> None:
        self.repo.set_human_review_required(
            active_run_id,
            True,
            ["CONVERSATION_QUOTA_EXCEEDED"],
        )
        self.repo.update_status(active_run_id, "awaiting_human_review")
        self.repo.update_conversation_status(conv_id, "frozen")
        self.repo.append_lui_message(
            conv_id,
            role="agent",
            content=(
                "⛔ 已达到本轮最大自动修改次数（5 次）。\n"
                "系统已通知专家介入，请等待专家审核。\n"
                "专家驳回后，你将获得新的 5 次修改机会。"
            ),
        )

    def _patch_skill_md(self, staging_path: Path, updates: dict) -> bool:
        skill_md = Path(staging_path) / "SKILL.md"
        if not skill_md.exists():
            return False

        content = skill_md.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return False
        parts = content.split("---", 2)
        if len(parts) < 3:
            return False

        frontmatter = yaml.safe_load(parts[1]) or {}
        if not isinstance(frontmatter, dict):
            return False
        updated = dict(frontmatter)
        updated.update(updates)
        if updated == frontmatter:
            return False

        body = parts[2]
        fm_text = yaml.safe_dump(
            updated,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        skill_md.write_text(f"---\n{fm_text}---{body}", encoding="utf-8")
        return True

    def _write_cases(self, staging_path: Path, cases: list[dict]) -> list[str]:
        staging_path = Path(staging_path)
        eval_cases_dir = staging_path / "eval_cases"
        sample_io_dir = staging_path / "sample_io"
        eval_cases_dir.mkdir(parents=True, exist_ok=True)
        sample_io_dir.mkdir(parents=True, exist_ok=True)

        existing = list(eval_cases_dir.glob("lui_*.yaml"))
        start_idx = len(existing)
        files_written: list[str] = []

        for offset, case in enumerate(cases):
            if not isinstance(case, dict):
                continue
            case_type = str(case.get("type", "happy_path"))
            abbr = _TYPE_ABBR.get(case_type, case_type)
            case_id = f"lui_{abbr}_{start_idx + offset:02d}"

            yaml_data = {
                "id": case_id,
                "type": case_type,
                "origin": "lui_agent",
                "user_intent": str(case.get("user_intent", "")),
                "input_template": str(case.get("input_template", "")),
                "expected_behavior": str(case.get("expected_behavior", "")),
            }
            yaml_path = eval_cases_dir / f"{case_id}.yaml"
            yaml_path.write_text(
                yaml.safe_dump(
                    yaml_data,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            sample_io_path = sample_io_dir / f"{case_id}.json"
            sample_io_path.write_text(
                json.dumps({"input": "", "output": None}, ensure_ascii=False),
                encoding="utf-8",
            )

            files_written.append(f"eval_cases/{case_id}.yaml")
            files_written.append(f"sample_io/{case_id}.json")

        return files_written

    def _tree_hash(self, root: Path) -> str:
        root = Path(root)
        if not root.exists():
            return ""
        digest = hashlib.sha256()
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = path.relative_to(root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

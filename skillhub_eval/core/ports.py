from typing import Protocol, runtime_checkable

from .schemas import EvaluationReport


@runtime_checkable
class Repository(Protocol):
    def init_db(self) -> None: ...

    def create_run(
        self,
        skill_id: str,
        skill_bundle_path: str,
        bundle_state: str,
        evaluation_mode: str,
        conversation_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> str: ...

    def create_conversation(
        self,
        skill_id: str,
        source: str,
        max_auto_runs: int = 5,
        source_path: str = "",
    ) -> str: ...

    def increment_auto_run_count(self, conversation_id: str) -> int: ...

    def reset_auto_run_count(self, conversation_id: str) -> None: ...

    def set_conversation_auto_confirmed(self, conversation_id: str, value: bool) -> None: ...

    def set_pending_patch(self, conversation_id: str, patch: dict) -> None: ...

    def get_pending_patch(self, conversation_id: str) -> dict | None: ...

    def clear_pending_patch(self, conversation_id: str) -> None: ...

    def get_clarifications(self, conversation_id: str) -> dict | None: ...

    def merge_clarifications(self, conversation_id: str, patch: dict) -> None: ...

    def get_plan_enrichment(self, conversation_id: str) -> dict | None: ...

    def set_plan_enrichment(self, conversation_id: str, payload: dict) -> None: ...

    def supersede_run(self, old_run_id: str, new_run_id: str) -> None: ...

    def get_lui_messages(self, conversation_id: str) -> list[dict]: ...

    def get_conversation(
        self,
        conversation_id: str,
    ) -> dict | None: ...

    def update_conversation_status(
        self,
        conversation_id: str,
        status: str,
    ) -> None: ...

    def set_conversation_skill_id(self, conversation_id: str, skill_id: str) -> None: ...

    def append_lui_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        run_id: str | None = None,
        message_type: str = "text",
        payload_json: dict | None = None,
    ) -> None: ...

    def list_conversations(
        self,
        limit: int = 50,
        pending_review: bool | None = None,
    ) -> list[dict]: ...

    def has_rich_report_for_run(self, conversation_id: str, run_id: str) -> bool: ...

    def update_status(self, run_id: str, status: str, **kwargs) -> None: ...

    def append_stage(self, run_id: str, stage: str, metadata: dict | None = None) -> None: ...

    def get_stage_progress(self, run_id: str) -> list[str]: ...

    def save_report(self, run_id: str, report: EvaluationReport) -> None: ...

    def get_run(self, run_id: str) -> dict | None: ...

    def get_report(self, run_id: str) -> dict | None: ...

    def patch_report_after_human_review(
        self,
        run_id: str,
        action: str,
        operator: str,
        comment: str,
        review_status: str,
    ) -> None: ...

    def list_history(
        self,
        limit: int = 50,
        human_review_required: bool | None = None,
    ) -> list[dict]: ...

    def save_gaps(self, run_id: str, gaps_json: dict) -> None: ...

    def get_gaps(self, skill_id: str) -> dict | None: ...

    def save_votes(self, run_id: str, votes: list[dict]) -> None: ...

    def get_votes_for_run(self, run_id: str) -> list[dict]: ...

    def save_human_review(
        self,
        run_id: str,
        action: str,
        operator: str,
        comment: str,
        preserved_votes: list[dict],
    ) -> None: ...

    def save_confirmation(
        self,
        skill_id: str,
        field_path: str,
        confirmed_value: str,
        operator: str,
    ) -> None: ...

    def get_confirmations(self, skill_id: str) -> dict[str, str]: ...

    def set_human_review_required(
        self,
        run_id: str,
        required: bool,
        trigger_codes: list[str],
    ) -> None: ...

    def log_event(self, run_id: str, event_name: str, payload: dict) -> None: ...

    def get_provider_errors(self, run_id: str) -> list[dict]: ...

    def get_stage_timings(self, run_id: str) -> list[dict]: ...

    def get_stage_timing_summaries(self, run_ids: list[str]) -> dict[str, dict]: ...

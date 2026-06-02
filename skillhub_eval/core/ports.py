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
    ) -> str: ...

    def update_status(self, run_id: str, status: str, **kwargs) -> None: ...

    def append_stage(self, run_id: str, stage: str, metadata: dict | None = None) -> None: ...

    def save_report(self, run_id: str, report: EvaluationReport) -> None: ...

    def get_run(self, run_id: str) -> dict | None: ...

    def get_report(self, run_id: str) -> dict | None: ...

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

    def set_human_review_required(
        self,
        run_id: str,
        required: bool,
        trigger_codes: list[str],
    ) -> None: ...

    def log_event(self, run_id: str, event_name: str, payload: dict) -> None: ...

"""Normalized local agent runtime events."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentEventType(StrEnum):
    TEXT_DELTA = "text_delta"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_WRITE = "file_write"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"
    RAW_UNSUPPORTED = "raw_unsupported"


class ToolResultPayload(BaseModel):
    tool: str
    command: str | None = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class AgentEvent(BaseModel):
    type: AgentEventType
    payload: dict[str, Any] | ToolResultPayload = Field(default_factory=dict)

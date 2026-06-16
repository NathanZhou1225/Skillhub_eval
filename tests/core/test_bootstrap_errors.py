"""Bootstrap failure user messaging."""

from skillhub_eval.core.bootstrap_errors import (
    append_bootstrap_failure,
    format_bootstrap_failure_reply,
    is_security_blocked_detail,
    security_blocked_gate_payload,
)


def test_is_security_blocked_detail():
    assert is_security_blocked_detail({"security_status": "blocked"})
    assert not is_security_blocked_detail({"security_status": "passed"})
    assert not is_security_blocked_detail("blocked")


def test_security_blocked_gate_payload_includes_reason():
    detail = {
        "security_status": "blocked",
        "security_findings": [
            {
                "finding_type": "PROMPT_INJECTION",
                "finding_type_zh": "提示注入风险",
                "source": "skill_bundle",
                "hint_zh": "请修改正文。",
            }
        ],
    }
    payload = security_blocked_gate_payload(detail)
    assert payload["security_status"] == "blocked"
    assert payload["security_block_reason_zh"]
    assert "提示注入风险" in payload["security_block_reason_zh"]


def test_format_bootstrap_failure_reply_not_raw_dict():
    detail = {
        "security_status": "blocked",
        "security_findings": [
            {"finding_type_zh": "提示注入风险", "source": "skill_bundle"}
        ],
    }
    text = format_bootstrap_failure_reply(detail)
    assert "评估未能启动" in text
    assert "security_status" not in text
    assert "{" not in text


def test_format_bootstrap_failure_reply_string():
    assert "上传错误" in format_bootstrap_failure_reply("上传错误")


def test_append_bootstrap_failure_security_blocked_message_type():
    class _Repo:
        def __init__(self):
            self.calls = []

        def append_lui_message(self, *args, **kwargs):
            self.calls.append(kwargs)

    repo = _Repo()
    detail = {
        "security_status": "blocked",
        "security_findings": [
            {
                "finding_type_zh": "提示注入风险",
                "source": "skill_bundle",
                "hint_zh": "改为拒绝此类请求。",
            }
        ],
    }
    append_bootstrap_failure(repo, "conv-1", detail)
    assert len(repo.calls) == 1
    call = repo.calls[0]
    assert call["message_type"] == "security_blocked"
    assert call["payload_json"]["security_findings"]
    assert call["payload_json"]["security_block_reason_zh"]

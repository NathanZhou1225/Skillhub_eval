"""Wave 5.3 Task 2 — unified confirm lexicon."""

from skillhub_eval.core.confirm_lexicon import (
    is_confirm_message,
    is_draft_confirm_message,
)
from skillhub_eval.core.lui_agent import LuiAgent
from skillhub_eval.core.skill_id_resolver import is_confirm_reply


def test_is_confirm_message_includes_queding():
    assert is_confirm_message("确定")
    assert is_confirm_message("  确定  ")
    assert is_confirm_message("确认")
    assert is_confirm_message("OK")
    assert is_confirm_message("yes")


def test_is_confirm_message_rejects_empty_and_unrelated():
    assert not is_confirm_message("")
    assert not is_confirm_message("   ")
    assert not is_confirm_message("把描述改短一点")


def test_skill_id_resolver_delegates_to_lexicon():
    assert is_confirm_reply("确定")
    assert is_confirm_reply("确认")
    assert not is_confirm_reply("名称不对")


def test_draft_confirm_prefixes_and_lexicon():
    assert is_draft_confirm_message("按这个补")
    assert is_draft_confirm_message("按这个补 eval_cases")
    assert LuiAgent.is_draft_confirmation("确定")
    assert LuiAgent.is_draft_confirmation("可以，按这个来")
    assert not LuiAgent.is_draft_confirmation("把描述改短一点")

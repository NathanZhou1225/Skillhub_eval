from skillhub_eval.core.usage import (
    UsageRecord,
    build_usage_summary,
    normalize_usage,
)


def test_normalize_usage_standard_keys():
    usage = normalize_usage(
        {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}
    )
    assert usage == {
        "prompt_tokens": 10,
        "completion_tokens": 3,
        "total_tokens": 13,
    }


def test_normalize_usage_legacy_keys():
    usage = normalize_usage({"input_tokens": 5, "output_tokens": 7})
    assert usage == {
        "prompt_tokens": 5,
        "completion_tokens": 7,
        "total_tokens": 12,
    }


def test_build_usage_summary_groups_rows_and_totals():
    summary = build_usage_summary(
        [
            UsageRecord(
                stage="model_judging",
                provider_label="DeepSeek",
                model="deepseek-chat",
                case_id="h1",
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            ),
            UsageRecord(
                stage="local_agent",
                provider_label="Cursor Agent",
                model="gpt-5",
                case_id="h1",
                usage={
                    "prompt_tokens": 4,
                    "completion_tokens": 1,
                    "total_tokens": 5,
                },
            ),
        ]
    )

    assert summary.totals.prompt_tokens == 14
    assert summary.totals.completion_tokens == 3
    assert summary.totals.total_tokens == 17
    assert summary.partial is False
    assert len(summary.by_stage) == 2

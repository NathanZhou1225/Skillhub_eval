"""One-off connectivity check for judge Provider A/B (reads .env via settings)."""

from __future__ import annotations

import asyncio
import sys

from skillhub_eval.providers.factory import build_judge_providers
from skillhub_eval.settings import settings

PROMPT = (
    "Connectivity check only. Reply with ONLY valid JSON, no markdown. "
    "Use any integer 0-100 for score — do NOT copy a fixed example value. "
    '{"sub_scores":{"step_completeness":{"score":<your integer>,"pass":true,'
    '"reason":"ok","evidence_refs":[]}},'
    '"confidence":"high","dimension_notes":"connectivity-test"}'
)


def key_ok(val: str) -> bool:
    return bool(val and val.strip() and "your_" not in val.lower())


async def test_provider(label: str, provider) -> tuple[bool, str]:
    try:
        result = await provider.judge(PROMPT)
        if isinstance(result, dict) and "sub_scores" in result:
            return True, f"{label}: OK"
        return False, f"{label}: unexpected response shape"
    except Exception as exc:
        return False, f"{label}: FAIL - {exc}"


async def main() -> None:
    provider_a, provider_b = build_judge_providers(settings)
    print("=== Provider connectivity (judge slots A/B) ===")
    a_ok = key_ok(provider_a.api_key)
    b_ok = key_ok(provider_b.api_key)
    print(f"{provider_a.label} API key set: {a_ok}")
    print(f"{provider_b.label} API key set: {b_ok}")
    if not a_ok or not b_ok:
        print("Fill JUDGE_PROVIDER_A/B_API_KEY (or legacy DEEPSEEK/GEMINI keys) in .env and retry.")
        sys.exit(1)

    results = await asyncio.gather(
        test_provider(provider_a.label, provider_a),
        test_provider(provider_b.label, provider_b),
    )
    for ok, msg in results:
        print(msg)
        if not ok:
            sys.exit(1)
    print("All providers connected.")


if __name__ == "__main__":
    asyncio.run(main())

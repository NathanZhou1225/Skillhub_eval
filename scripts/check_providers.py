"""One-off connectivity check for DeepSeek + Gemini (reads .env via settings)."""

from __future__ import annotations

import asyncio
import sys

from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.gemini import GeminiProvider
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
    print("=== Provider connectivity ===")
    ds_ok = key_ok(settings.deepseek_api_key)
    gm_ok = key_ok(settings.gemini_api_key)
    print(f"DEEPSEEK_API_KEY set: {ds_ok}")
    print(f"GEMINI_API_KEY set: {gm_ok}")
    if not ds_ok or not gm_ok:
        print("Fill both keys in .env and retry.")
        sys.exit(1)

    ds = DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    gm = GeminiProvider(
        api_key=settings.gemini_api_key,
        base_url=settings.gemini_base_url,
        model=settings.gemini_model,
    )

    results = await asyncio.gather(
        test_provider("DeepSeek", ds),
        test_provider("Gemini", gm),
    )
    for ok, msg in results:
        print(msg)
        if not ok:
            sys.exit(1)
    print("All providers connected.")


if __name__ == "__main__":
    asyncio.run(main())

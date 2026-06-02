"""
Abstract base for all LLM judge providers.

core/ depends ONLY on this base — never on DeepSeekProvider or GeminiProvider
directly. This is the hexagonal architecture seam for LLM calls.
"""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """
    Minimal contract for all LLM quality-review judges.

    Implementations must:
    - Be async (returns a coroutine).
    - Return a parsed JSON dict matching the §7 Prompt output contract:
        {
          "sub_scores": { "<criterion_id>": {"score": int, "pass": bool,
                          "reason": str, "evidence_refs": list} },
          "confidence": "low" | "medium" | "high",
          "dimension_notes": str
        }
    - Raise RuntimeError on unrecoverable failure after all retries.
    - Never import FastAPI, SQLite, or other infrastructure concerns.
    """

    @abstractmethod
    async def judge(self, prompt: str) -> dict:
        """
        Send the assembled rubric prompt to the LLM and return parsed JSON.

        Args:
            prompt: Full evaluation prompt (§7 format, assembled by model_judge).

        Returns:
            Parsed dict with sub_scores, confidence, dimension_notes.

        Raises:
            RuntimeError: If the provider fails after all retries.
        """

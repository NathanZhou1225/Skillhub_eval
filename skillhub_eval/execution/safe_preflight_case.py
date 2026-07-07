"""Automatic safe local execution check case generation and formal-case helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import yaml

from skillhub_eval.core.ingest import ingest_bundle, is_preflight_case

GENERATED_CASE_ID = "runtime_preflight_01"
GENERATED_CASE_FILENAME = "runtime_preflight_01.yaml"

_UNSAFE_ACTION_TERMS = re.compile(
    r"(买入|卖出|下单|交易|支付|删除|发送|发布|"
    r"buy|sell|order|payment|delete|send|publish|purchase|trade)",
    re.IGNORECASE,
)

_ENV_CHECK_MARKERS = re.compile(
    r"(环境检查|执行环境|仅验证|不生成真实|不输出.*业务|"
    r"environment check|check only|no real)",
    re.IGNORECASE,
)

_REQUIRED_FIELDS = ("id", "user_intent", "input_template", "expected_behavior")


def formal_eval_cases(bundle: dict) -> list[dict]:
    return [c for c in bundle.get("eval_cases") or [] if not is_preflight_case(c)]


def validate_safe_preflight_candidate(candidate: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if candidate.get("type") != "preflight":
        reasons.append("type_must_be_preflight")
    if candidate.get("safe_preflight") is not True:
        reasons.append("safe_preflight_required")
    for field in _REQUIRED_FIELDS:
        value = candidate.get(field)
        if not value or not str(value).strip():
            reasons.append(f"missing_{field}")
    combined = " ".join(
        str(candidate.get(key, "")) for key in ("user_intent", "input_template", "expected_behavior")
    )
    for field in ("user_intent", "expected_behavior"):
        if _UNSAFE_ACTION_TERMS.search(str(candidate.get(field, ""))):
            reasons.append("unsafe_action_terms")
            break
    if not _ENV_CHECK_MARKERS.search(combined):
        reasons.append("missing_environment_check_framing")
    return (len(reasons) == 0, reasons)


def fallback_safe_preflight_case(bundle: dict) -> dict:
    skill_name = str(bundle.get("name") or bundle.get("skill_id") or "当前 Skill")
    return {
        "id": GENERATED_CASE_ID,
        "type": "preflight",
        "safe_preflight": True,
        "origin": "runtime_platform_template",
        "user_intent": (
            f"仅验证本地执行链路能读取 {skill_name} 指令并返回最小可评估结果，"
            "不生成真实业务结论。"
        ),
        "input_template": (
            "请仅进行本地执行环境检查：读取当前 Skill 指令，返回最小结构化结果；"
            "必须说明这是环境检查，不输出买卖、下单、发送、删除、支付或其他真实业务建议。"
        ),
        "expected_behavior": (
            "能读取 Skill 指令并返回符合声明输出要求的最小结果；"
            "如 Skill 需要入口脚本，应观察到入口或工具调用证据；输出包含必要免责声明。"
        ),
    }


def _resolve_risk_level(bundle: dict, locked_risk_level: str | None = None) -> str:
    return str(
        locked_risk_level
        or bundle.get("risk_level_locked")
        or bundle.get("risk_level_declared")
        or bundle.get("risk_level")
        or "low"
    ).lower()


def build_safe_preflight_case(
    bundle: dict,
    candidate_generator: Callable[[dict], dict | None] | None = None,
    *,
    locked_risk_level: str | None = None,
) -> dict | None:
    risk = _resolve_risk_level(bundle, locked_risk_level)
    if risk != "high":
        return None
    if any(is_preflight_case(c) for c in bundle.get("eval_cases") or []):
        return None
    if candidate_generator is not None:
        try:
            candidate = candidate_generator(bundle)
        except Exception:
            candidate = None
        if isinstance(candidate, dict):
            normalized = {
                **candidate,
                "id": GENERATED_CASE_ID,
                "type": "preflight",
                "safe_preflight": True,
            }
            ok, _reasons = validate_safe_preflight_candidate(normalized)
            if ok:
                return {
                    **normalized,
                    "origin": "runtime_platform_llm",
                }
    return fallback_safe_preflight_case(bundle)


def _write_case_yaml(path: Path, case: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(case, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _load_case_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _authored_preflight_cases(bundle: dict) -> list[dict]:
    authored: list[dict] = []
    for case in bundle.get("eval_cases") or []:
        if not is_preflight_case(case):
            continue
        origin = str(case.get("origin") or "")
        if case.get("id") != GENERATED_CASE_ID or not origin.startswith("runtime_platform"):
            authored.append(case)
    return authored


def ensure_safe_preflight_case(
    bundle_path: str | Path,
    *,
    force: bool = False,
    locked_risk_level: str | None = None,
    candidate_generator: Callable[[dict], dict | None] | None = None,
) -> dict | None:
    root = Path(bundle_path)
    bundle = ingest_bundle(str(root))
    target = root / "eval_cases" / GENERATED_CASE_FILENAME

    if _authored_preflight_cases(bundle):
        if force:
            raise ValueError("cannot force-regenerate: authored safe preflight case exists")
        return None

    if not force and any(is_preflight_case(c) for c in bundle.get("eval_cases") or []):
        return None

    if force and target.is_file():
        existing = _load_case_yaml(target)
        origin = str(existing.get("origin") or "")
        if not origin.startswith("runtime_platform"):
            raise ValueError("cannot force-regenerate: runtime_preflight_01.yaml is not system-generated")
        target.unlink()

    if force:
        bundle = ingest_bundle(str(root))

    case = build_safe_preflight_case(
        bundle,
        candidate_generator=candidate_generator,
        locked_risk_level=locked_risk_level,
    )
    if case is None:
        return None

    _write_case_yaml(target, case)
    return case

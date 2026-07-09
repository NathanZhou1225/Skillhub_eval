"""Automatic safe local execution check case generation and formal-case helpers."""

from __future__ import annotations

import re
from pathlib import Path

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

# Reject preflight cases that mirror formal skill workflows (e.g. full stock diagnosis).
_HEAVY_PREFLIGHT_SCOPE = re.compile(
    r"(诊断|个股|股票代码|\b\d{6}\b|diagnosis_bundle|六维|"
    r"run_diagnosis|akshare|pipeline\.sh|benchmark_sector|"
    r"强烈推荐|买入|卖出|加仓|止盈)",
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
    if _HEAVY_PREFLIGHT_SCOPE.search(combined):
        reasons.append("heavy_business_scope")
    return (len(reasons) == 0, reasons)


def fallback_safe_preflight_case(bundle: dict) -> dict:
    skill_name = str(bundle.get("name") or bundle.get("skill_id") or "当前 Skill")
    has_entrypoint = bool(bundle.get("has_scripts") and bundle.get("entrypoint"))
    if has_entrypoint:
        input_template = (
            "请仅进行本地执行环境检查：读取当前 Skill 指令，确认 SKILL.md 与声明入口文件存在；"
            "可做无副作用的入口文件可见性或语法检查；不运行正式业务流程，"
            "不取数，不输出买卖、下单、发送、删除、支付或其他真实业务建议。"
        )
        expected_behavior = (
            "返回最小结构化结果，至少说明 preflight=true、skill_readable、entrypoint_visible；"
            "如调用工具，应只体现入口文件检查证据，不产生真实业务结论。"
        )
    else:
        input_template = (
            "请仅进行本地执行环境检查：确认当前目录存在 SKILL.md，读取当前 Skill 指令，"
            "返回最小结构化结果；必须说明这是环境检查，不输出买卖、下单、发送、删除、支付或其他真实业务建议。"
        )
        expected_behavior = (
            "能读取 Skill 指令并返回最小结构化结果，至少说明 preflight=true、skill_readable；"
            "输出包含必要免责声明，不产生真实业务结论。"
        )
    return {
        "id": GENERATED_CASE_ID,
        "type": "preflight",
        "safe_preflight": True,
        "origin": "runtime_platform_template",
        "user_intent": (
            f"仅验证本地执行链路能读取 {skill_name} 指令并返回最小可评估结果，"
            "不生成真实业务结论。"
        ),
        "input_template": input_template,
        "expected_behavior": expected_behavior,
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
    *,
    locked_risk_level: str | None = None,
) -> dict | None:
    risk = _resolve_risk_level(bundle, locked_risk_level)
    if risk != "high":
        return None
    if any(is_preflight_case(c) for c in bundle.get("eval_cases") or []):
        return None
    return fallback_safe_preflight_case(bundle)


async def ensure_safe_preflight_case_with_provider(
    bundle_path: str | Path,
    *,
    provider=None,
    force: bool = False,
    locked_risk_level: str | None = None,
) -> dict | None:
    _ = provider
    root = Path(bundle_path)
    bundle = ingest_bundle(str(root))
    if _resolve_risk_level(bundle, locked_risk_level) != "high":
        return ensure_safe_preflight_case(
            root,
            force=force,
            locked_risk_level=locked_risk_level,
        )
    if _authored_preflight_cases(bundle):
        return ensure_safe_preflight_case(
            root,
            force=force,
            locked_risk_level=locked_risk_level,
        )
    if not force and any(is_preflight_case(c) for c in bundle.get("eval_cases") or []):
        return None
    return ensure_safe_preflight_case(
        root,
        force=force,
        locked_risk_level=locked_risk_level,
    )


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


def _should_replace_generated_preflight(case: dict) -> bool:
    origin = str(case.get("origin") or "")
    if not origin.startswith("runtime_platform"):
        return False
    if origin == "runtime_platform_llm":
        return True
    ok, _reasons = validate_safe_preflight_candidate(case)
    return not ok


def ensure_safe_preflight_case(
    bundle_path: str | Path,
    *,
    force: bool = False,
    locked_risk_level: str | None = None,
) -> dict | None:
    root = Path(bundle_path)
    bundle = ingest_bundle(str(root))
    target = root / "eval_cases" / GENERATED_CASE_FILENAME

    if _authored_preflight_cases(bundle):
        if force:
            raise ValueError("cannot force-regenerate: authored safe preflight case exists")
        return None

    if not force and any(is_preflight_case(c) for c in bundle.get("eval_cases") or []):
        if target.is_file():
            existing = _load_case_yaml(target)
            if _should_replace_generated_preflight(existing):
                target.unlink()
                bundle = ingest_bundle(str(root))
            else:
                return None
        else:
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
        locked_risk_level=locked_risk_level,
    )
    if case is None:
        return None

    _write_case_yaml(target, case)
    return case

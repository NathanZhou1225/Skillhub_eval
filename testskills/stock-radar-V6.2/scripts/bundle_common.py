"""Shared constants and helpers for stock-radar diagnosis bundle pipeline."""
from __future__ import annotations

from pathlib import Path

SCHEMA_VERSION = "1.2.1"

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SKILL_ROOT / "schemas" / "diagnosis_bundle.schema.json"

DIMENSION_ORDER = [
    "基本面",
    "技术面",
    "资金面",
    "消息面",
    "概念 / 产业链",
    "市场环境",
]

STATE_CORE_MATRIX: dict[str, list[str]] = {
    "个股异动态": ["消息面", "资金面"],
    "板块共振态": ["概念 / 产业链", "市场环境"],
    "活跃热点态": ["消息面", "概念 / 产业链"],
    "阶段切换态": ["资金面", "市场环境"],
    "平静无驱动态": ["基本面", "概念 / 产业链"],
}

# HTML radar chart emphasis (render-only; never in agent bundle)
STATE_RADAR_CORE_WEIGHTS: dict[str, dict[str, int]] = {
    "个股异动态": {"消息面": 95, "资金面": 92},
    "板块共振态": {"概念 / 产业链": 93, "市场环境": 90},
    "活跃热点态": {"消息面": 94, "概念 / 产业链": 91},
    "阶段切换态": {"资金面": 92, "市场环境": 90},
    "平静无驱动态": {"基本面": 90, "概念 / 产业链": 88},
}

RADAR_SECONDARY_WEIGHT = 30
RADAR_CORE_DEFAULT_WEIGHT = 88
RADAR_TECHNICAL_EVOLUTION_WEIGHT = 48

J_HEADERS = {
    "j1": "J1 主驱动 · 是什么在推这只票",
    "j2": "J2 还能涨多久",
    "j3": "J3 现在处于哪个阶段",
    "j4": "J4 是跟板块还是独立走",
    "j5": "J5 主要风险点",
}

SEPARATOR = "———"

DISCLAIMER = (
    "以上分析基于公开数据，仅供投顾内部参考，不构成投资建议；"
    "本文不涉及具体买卖点位与目标价；"
    "最终投资决策需结合客户风险承受能力与投顾独立判断。"
)

SECONDARY_CONCLUSION = "非当前主导。"
SECONDARY_INTERPRETATION = "不作交易参考。"

BANNED_EVOLUTION_WORDS = ("升级", "降级")

TECHNICAL_PRICE_BANNED = (
    "MA5",
    "MA20",
    "MA60",
    "MA120",
    "支撑位",
    "阻力位",
    "止损位",
    "目标价",
    "止盈点",
)

TRADING_BANNED_PHRASES = (
    "建议买入",
    "建议卖出",
    "建议加仓",
    "建议减仓",
    "建议持有",
    "建议观望",
    "建议看多",
    "建议看空",
    "必须买入",
    "必须卖出",
    "立即买入",
    "立即卖出",
)

THEME_WORD_LIMITS = {
    "分歧兑现": 2,
    "情绪退潮": 2,
    "次日承接": 2,
    "异动公告": 2,
    "估值无锚": 2,
    "板块共振": 2,
    "高低切换": 2,
    "共识充分": 2,
    "流动性博弈": 2,
    "放量突破": 2,
}

DEFAULT_FETCH_DIR = Path("/tmp/stock-radar")
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output" / "diagnosis"


def all_dimension_keys() -> set[str]:
    return set(DIMENSION_ORDER)


def expected_core_dimensions(state_primary: str) -> list[str]:
    return list(STATE_CORE_MATRIX[state_primary])


def compute_radar_weights(bundle: dict) -> dict[str, int]:
    """Derive 6-dimension radar emphasis from state + core_dimensions (render-only)."""
    judgment = bundle["judgment"]
    state = judgment["state_primary"]
    core_dims = set(judgment["core_dimensions"])
    profile = STATE_RADAR_CORE_WEIGHTS.get(state, {})
    tech_block = bundle["narrative"]["dimensions"]["技术面"]

    weights: dict[str, int] = {}
    for dim in DIMENSION_ORDER:
        if dim in core_dims:
            weights[dim] = profile.get(dim, RADAR_CORE_DEFAULT_WEIGHT)
        elif (
            dim == "技术面"
            and judgment.get("technical_evolution")
            and tech_block.get("role") == "secondary_technical"
        ):
            weights[dim] = RADAR_TECHNICAL_EVOLUTION_WEIGHT
        else:
            weights[dim] = RADAR_SECONDARY_WEIGHT
    return weights


def format_change_pct(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    if value > 0 and not text.startswith("+"):
        return f"+{text}"
    return text


def collect_narrative_text(bundle: dict) -> str:
    parts = [
        bundle["narrative"]["summary_hook"],
        bundle["narrative"]["client_brief"],
    ]
    for dim in DIMENSION_ORDER:
        block = bundle["narrative"]["dimensions"][dim]
        parts.extend([block["conclusion"], block["interpretation"], *block["data_bullets"]])
    j = bundle["judgments_j"]
    parts.extend([j["j1"], j["j2"], j["j3"], j["j4"], j["j5"]])
    return "\n".join(parts)

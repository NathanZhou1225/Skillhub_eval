"""
§6.4 DSL Assertion Engine (C-1, grill-me 2026-06-02).

Protocol operators (8):
    ==  !=  exists  not_exists  is_array  is_string  is_number  contains

Extension operators (2, not in protocol, extra support):
    regex_match  numeric_range

Expression format (protocol §6.4):
    {path} {operator} {value}

    path    — dot-separated; root object is `response`
    value   — string in single quotes | boolean true/false | number (no quotes)

Examples:
    response.status == 'success'
    response.abnormal_days is_array
    response.error_code exists
    response.count numeric_range 10 100
"""

from __future__ import annotations

import re
from typing import Any


class DslParseError(ValueError):
    """Raised when a DSL expression cannot be parsed."""


# Protocol operators that take NO value argument
_UNARY_OPS = {"exists", "not_exists", "is_array", "is_string", "is_number"}

# All supported operators (protocol first, then extensions)
_ALL_OPS = {
    "==", "!=",
    "exists", "not_exists",
    "is_array", "is_string", "is_number",
    "contains",
    "regex_match",
    "numeric_range",
}

# Regex to tokenize the DSL expression
# Groups: (path)(operator)(optional value)
_EXPR_RE = re.compile(
    r"^(\S+)\s+"                        # path (non-whitespace)
    r"(==|!=|not_exists|is_array|is_string|is_number|exists|"
    r"contains|regex_match|numeric_range)"  # operator
    r"(?:\s+(.+))?$",                   # optional value
    re.DOTALL,
)


def _resolve_path(obj: Any, path: str) -> tuple[bool, Any]:
    """
    Walk dot-separated path starting from the root `response` key.
    Returns (found: bool, value).
    Path must start with 'response'; e.g. 'response.status'.
    """
    parts = path.split(".")
    if parts[0] != "response":
        raise DslParseError(f"Path must start with 'response', got: {path!r}")
    current = obj
    for part in parts[1:]:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _parse_value(raw: str | None) -> Any:
    """
    Parse a DSL value token into a Python object.
      'text'  → str
      true    → True
      false   → False
      42      → int
      3.14    → float
    """
    if raw is None:
        return None
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw  # fallback: treat as bare string


def _fail(assertion_id: str, detail: str, reason_code: str = "ASSERTION_DSL_FAIL") -> dict:
    return {
        "assertion_id": assertion_id,
        "passed": False,
        "reason_code": reason_code,
        "detail": detail,
    }


def _pass(assertion_id: str) -> dict:
    return {
        "assertion_id": assertion_id,
        "passed": True,
        "reason_code": None,
        "detail": "",
    }


class DslEngine:
    """
    Evaluates §6.4 DSL assertion expressions against a JSON `actual_output` dict.

    Usage:
        engine = DslEngine()
        result = engine.evaluate("response.status == 'success'", actual_output)
        results = engine.evaluate_all(assertions, actual_output, case_id="c01")
    """

    def evaluate(self, expression: str, actual_output: dict) -> dict:
        """
        Evaluate a single DSL expression.

        Returns dict with: assertion_id, passed, reason_code, detail.
        Raises DslParseError for unparseable expressions.
        """
        expression = expression.strip()
        match = _EXPR_RE.match(expression)
        if not match:
            raise DslParseError(f"Cannot parse DSL expression: {expression!r}")

        path, operator, raw_value = match.group(1), match.group(2), match.group(3)
        assertion_id = f"{path}:{operator}"

        # Validate operator
        if operator not in _ALL_OPS:
            raise DslParseError(f"Unknown operator {operator!r} in: {expression!r}")

        # Unary operators don't use value
        if operator in _UNARY_OPS and raw_value is not None:
            # Allow trailing whitespace/tokens but ignore them for unary
            pass

        # Resolve path
        found, actual = _resolve_path(actual_output, path)

        # ── Protocol operators ────────────────────────────────────────────────

        if operator == "exists":
            if not found:
                return _fail(assertion_id, f"Field {path!r} does not exist in output")
            return _pass(assertion_id)

        if operator == "not_exists":
            if found:
                return _fail(assertion_id, f"Field {path!r} exists but should not")
            return _pass(assertion_id)

        if operator == "is_array":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found")
            if not isinstance(actual, list):
                return _fail(assertion_id, f"Field {path!r} is {type(actual).__name__}, not array")
            return _pass(assertion_id)

        if operator == "is_string":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found")
            if not isinstance(actual, str):
                return _fail(assertion_id, f"Field {path!r} is {type(actual).__name__}, not string")
            return _pass(assertion_id)

        if operator == "is_number":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found")
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return _fail(assertion_id, f"Field {path!r} is {type(actual).__name__}, not number")
            return _pass(assertion_id)

        # Value-bearing operators from here on
        value = _parse_value(raw_value)

        if operator == "==":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found; expected {value!r}")
            if actual != value:
                return _fail(assertion_id, f"{path!r}: expected {value!r}, got {actual!r}")
            return _pass(assertion_id)

        if operator == "!=":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found")
            if actual == value:
                return _fail(assertion_id, f"{path!r}: expected != {value!r}, but got {actual!r}")
            return _pass(assertion_id)

        if operator == "contains":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found")
            if isinstance(actual, str):
                needle = str(value)
                if needle not in actual:
                    return _fail(assertion_id, f"{path!r}: {needle!r} not in {actual!r}")
            elif isinstance(actual, list):
                if value not in actual:
                    return _fail(assertion_id, f"{path!r}: {value!r} not in list")
            else:
                return _fail(
                    assertion_id,
                    f"'contains' requires string or array, got {type(actual).__name__}",
                )
            return _pass(assertion_id)

        # ── Extension operators ───────────────────────────────────────────────

        if operator == "regex_match":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found")
            pattern = str(value)
            if not isinstance(actual, str):
                return _fail(assertion_id, f"regex_match requires string field; got {type(actual).__name__}")
            if not re.search(pattern, actual):
                return _fail(assertion_id, f"{path!r}: {actual!r} does not match pattern {pattern!r}")
            return _pass(assertion_id)

        if operator == "numeric_range":
            if not found:
                return _fail(assertion_id, f"Field {path!r} not found")
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return _fail(assertion_id, f"numeric_range requires numeric field; got {type(actual).__name__}")
            # raw_value: "10 100"
            try:
                parts = (raw_value or "").split()
                lo, hi = float(parts[0]), float(parts[1])
            except (IndexError, ValueError) as exc:
                raise DslParseError(
                    f"numeric_range requires two numbers; got: {raw_value!r}"
                ) from exc
            if not (lo <= actual <= hi):
                return _fail(
                    assertion_id,
                    f"{path!r}={actual} is outside range [{lo}, {hi}]",
                )
            return _pass(assertion_id)

        # Should never reach here due to regex guard above
        raise DslParseError(f"Unhandled operator {operator!r}")

    def evaluate_all(
        self,
        assertions: list[str],
        actual_output: dict,
        case_id: str = "",
    ) -> list[dict]:
        """
        Evaluate a list of DSL assertions, attaching case_id to each result.
        Parse errors produce a failed result (not a raised exception) so one bad
        assertion does not abort the entire batch.
        """
        results: list[dict] = []
        for expr in assertions:
            try:
                result = self.evaluate(expr, actual_output)
            except DslParseError as exc:
                result = _fail(f"{expr}:parse_error", str(exc), reason_code="ASSERTION_DSL_FAIL")
            result["case_id"] = case_id
            results.append(result)
        return results

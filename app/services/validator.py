import json
from pathlib import Path
import re


class GuardrailViolation(Exception):
    pass


_POLICY = None


def _load_policy() -> dict:
    global _POLICY
    if _POLICY is not None:
        return _POLICY
    policy_path = Path(__file__).resolve().parent.parent / "guardrails.json"
    default = {"deny_contains": ["delete ", "update ", "insert ", "drop ", "truncate ", " select * "]}
    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            _POLICY = json.load(f)
    except Exception:
        _POLICY = default
    return _POLICY


def ensure_safe(sql: str) -> None:
    lowered = f" {sql.lower()} "
    policy = _load_policy()
    deny = policy.get("deny_contains", [])
    if any(tok in lowered for tok in deny):
        raise GuardrailViolation("query violates guardrail policy")


def lint(sql: str):
    """Return list of issues: [{level, code, message}]"""
    issues = []
    lowered = sql.lower()
    if " select * " in f" {lowered} ":
        issues.append({"level": "error", "code": "no_select_star", "message": "SELECT * is not allowed"})
    # Heuristic: require some time filter for event-like tables
    if re.search(r"from\s+`?[^`]*events[^`]*`?", lowered) and not re.search(r"where\s+.*(date|time|\_table\_suffix)", lowered):
        issues.append({"level": "warning", "code": "missing_time_filter", "message": "events-like table without time filter"})
    return issues

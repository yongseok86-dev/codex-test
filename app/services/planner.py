from typing import Any, Dict


def make_plan(intent: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    plan: Dict[str, Any] = {"intent": intent, "slots": slots}
    # Resolve defaults
    plan.setdefault("metric", slots.get("metric", "orders"))
    plan.setdefault("grain", "day")
    return plan


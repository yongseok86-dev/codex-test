from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple
import yaml


def load_semantic_root() -> Dict[str, Any]:
    root = Path(__file__).resolve().parent
    model = {}
    for name in ["semantic.yml", "metrics_definitions.yaml", "golden_queries.yaml"]:
        p = root / name
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f) or {}
                    model[name] = data
                except Exception:
                    model[name] = {}
        else:
            model[name] = {}
    return model


def load_datasets_overrides() -> Dict[str, str]:
    root = Path(__file__).resolve().parent
    p = root / "datasets.yaml"
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {str(k): str(v) for k, v in (data or {}).items()}
    except Exception:
        return {}


def apply_table_overrides(semantic_model: Dict[str, Any], overrides: Dict[str, str]) -> Dict[str, Any]:
    """Return a shallow-copied semantic model with entity table names replaced by overrides.
    overrides keys: entity name or logical alias; values: fully-qualified table path.
    """
    model = dict(semantic_model)
    entities = [dict(e) for e in (model.get("entities") or [])]
    changed = False
    for e in entities:
        name = e.get("name")
        if name and name in overrides:
            e["table"] = overrides[name]
            changed = True
    if changed:
        model["entities"] = entities
    return model

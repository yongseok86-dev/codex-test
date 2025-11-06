from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
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


from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from app.semantic.loader import load_semantic_root, load_datasets_overrides, apply_table_overrides


@dataclass
class Column:
    name: str
    type: str
    sample: Optional[str] = None


@dataclass
class Table:
    name: str
    columns: List[Column] = field(default_factory=list)
    row_count: Optional[int] = None


@dataclass
class Catalog:
    tables: Dict[str, Table] = field(default_factory=dict)
    loaded_at: datetime = field(default_factory=datetime.utcnow)
    ttl_minutes: int = 30

    def expired(self) -> bool:
        return datetime.utcnow() - self.loaded_at > timedelta(minutes=self.ttl_minutes)


_CATALOG: Optional[Catalog] = None


def load_catalog(force: bool = False) -> Catalog:
    global _CATALOG
    if _CATALOG and not _CATALOG.expired() and not force:
        return _CATALOG

    sem_root = load_semantic_root()
    sem_raw = sem_root.get("semantic.yml", {}) or {}
    overrides = load_datasets_overrides()
    sem = apply_table_overrides(sem_raw, overrides) if isinstance(sem_raw, dict) else sem_raw

    tables: Dict[str, Table] = {}
    for e in (sem.get("entities") or []):
        tname = e.get("table")
        if not tname:
            continue
        cols = []
        for d in (e.get("dimensions") or []):
            cols.append(Column(name=d.get("name"), type=d.get("type") or "string"))
        for m in (e.get("measures") or []):
            cols.append(Column(name=m.get("name"), type="number"))
        tables[str(tname).lower()] = Table(name=str(tname), columns=cols)

    _CATALOG = Catalog(tables=tables)
    return _CATALOG


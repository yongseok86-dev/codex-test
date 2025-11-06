from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re
from app.semantic.loader import load_semantic_root, load_datasets_overrides, apply_table_overrides


def _tokenize(s: str) -> List[str]:
    return re.findall(r"[\w가-힣]+", s.lower())


def _similar_golden(question: str, semantic_root: Dict[str, Any], k: int = 3) -> List[Dict[str, Any]]:
    gq = semantic_root.get("golden_queries.yaml", {}) or {}
    items = gq.get("queries") or []
    if not items:
        return []
    q_tokens = set(_tokenize(question))
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for it in items:
        nl = str(it.get("nl", ""))
        score = len(q_tokens.intersection(_tokenize(nl)))
        scored.append((score, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for sc, it in scored[:k] if sc > 0]


def build_sql_prompt(question: str, semantic_root: Dict[str, Any]) -> str:
    sem_raw = semantic_root.get("semantic.yml", {})
    overrides = load_datasets_overrides()
    sem = apply_table_overrides(sem_raw, overrides) if isinstance(sem_raw, dict) else sem_raw
    metrics = semantic_root.get("metrics_definitions.yaml", {})
    vocab = sem.get("vocabulary", {}) if isinstance(sem, dict) else {}

    lines = []
    lines.append("You are an expert data analyst generating BigQuery SQL.")
    lines.append("Follow these rules strictly:")
    lines.append("- Use fully-qualified table names when present.")
    lines.append("- Prefer approximate functions (APPROX_*) only when requested.")
    lines.append("- Never use SELECT * ; select only necessary columns.")
    lines.append("- Output ONLY SQL in a code block. No explanations.")
    lines.append("")
    if sem:
        lines.append("Semantic model (entities/dimensions/measures):")
        lines.append(str(sem))
        lines.append("")
    if metrics:
        lines.append("Metric definitions:")
        lines.append(str(metrics))
        lines.append("")
    if vocab:
        lines.append("Vocabulary/Synonyms:")
        lines.append(str(vocab))
        lines.append("")
    # Add few-shot similar golden questions (NL + intent/slots)
    sims = _similar_golden(question, semantic_root)
    if sims:
        lines.append("Similar questions (with intended structure):")
        for s in sims:
            lines.append(str({"nl": s.get("nl"), "slots": s.get("slots"), "intent": s.get("intent")}))
        lines.append("")

    lines.append("Question:")
    lines.append(question)
    lines.append("")
    lines.append("Respond with:\n```sql\n<SQL>\n```")
    return "\n".join(lines)

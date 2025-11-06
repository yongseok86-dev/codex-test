from __future__ import annotations

from typing import Any, Dict


def build_sql_prompt(question: str, semantic: Dict[str, Any]) -> str:
    sem = semantic.get("semantic.yml", {})
    metrics = semantic.get("metrics_definitions.yaml", {})
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
    lines.append("Question:")
    lines.append(question)
    lines.append("")
    lines.append("Respond with:\n```sql\n<SQL>\n```")
    return "\n".join(lines)


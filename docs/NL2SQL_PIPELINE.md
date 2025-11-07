# NL→SQL Pipeline (Ordered, LLM Placement)

1) Input Normalization (Rule)
- Clean whitespace, simple synonym mapping via semantic vocabulary.
- Optional: Korean morphological analysis (future).

2) Session Context (Rule)
- Load conversation-scoped context: last SQL/plan, preferred filters.

3) Schema Understanding (Rule)
- Build in-memory catalog from semantic.yml (+ datasets.yaml overrides).
- Column aliases (app/schema/aliases.yaml).

4) Schema Linking (Rule → ML optional)
- Token/alias matching to tables/columns; produce candidates & confidence.
- (Optional future) Embedding similarity.

5) NLU Parsing (Rule → ML optional)
- Extract intent (metric/over_time/...), slots(metric, time_window, group_by, filters...).

6) Semantic Reconciliation (Rule)
- Validate metric/dimension existence; inject default filters; infer join path.

7) Planning (Rule)
- Decide grain, complete group_by/order_by/filters; set execution options.

8) SQL Generation (Hybrid)
- Easy queries: Template/Rule-based SQLGen.
- Complex queries: LLM generation with constrained prompt (semantic + metrics + golden few-shot) and whitelist guidance.
- Fallback: If LLM fails, use Rule-based.

9) Static Guardrails & Lint (Rule)
- Disallow DML/DDL, SELECT *; warn missing time filters.
- Parse SQL with sqlglot (BigQuery dialect).

10) Validation Pipeline (Rule)
- DRY RUN → EXPLAIN → LIMIT 0 schema → Canary → Domain assertions (time bucketing, time window, default filters, entity table, group_by present).

11) Repair Loop (LLM Optional)
- On pipeline failure or execution error: send (question, SQL, error) to LLM for a one-shot fix; re-validate.

12) Execute / Materialize (Rule)
- Dry-run only, full execution, or CTAS materialization with expiration.

13) Result Summarization (Rule → LLM Optional)
- Heuristic summary (rows/columns/cost); optional LLM natural-language summary.

14) Logging & Learning (Rule)
- Structured logs (intent/metric/provider/bytes/cost), SSE event stream, feedback data for future improvements.

LLM used at: 8 (SQLGen complex), 11 (Repair), 13 (Summary optional)

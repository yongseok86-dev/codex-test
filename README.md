# codex-test
typescript, vue3, elementplus ui framework

## NL2SQL Agent (Python) – scaffold

This repo also contains a minimal FastAPI scaffold for an NL→SQL agent targeting a BigQuery semantic layer.

- Run (dev):
  - Install: `pip install -e .[dev]` (or use `uv sync`)
  - Start: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- API:
  - `GET /healthz`, `GET /readyz`
  - `POST /api/query` { q: "지난 7일 주문 추이" }
- Tests: `pytest -q`

Note: execution defaults to dry-run mode. Configure via `.env` if needed.

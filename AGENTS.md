# Repository Guidelines

This repository currently has no predefined toolchain. Use the guidelines below to keep contributions consistent and easy to review. If the stack is introduced (e.g., Node/TypeScript or Python), follow the appropriate commands and patterns here.

## Project Structure & Module Organization
- `src/` — application/library code (organized by domain; small, focused modules).
- `tests/` — unit/integration tests mirroring `src/` structure.
- `scripts/` — local dev and CI helpers.
- `docs/` — long‑form documentation and ADRs.
- `assets/` — static files (images, samples, fixtures).

## Build, Test, and Development Commands
- Node (when `package.json` exists): `npm ci`, `npm run build`, `npm test`, `npm run dev`.
- Python (when `pyproject.toml` or `requirements.txt` exists): `python -m venv .venv` → activate → `pip install -r requirements.txt` → `pytest -q`.
- Format/lint (adopt per stack): JS/TS → ESLint + Prettier; Python → Ruff + Black.

## Coding Style & Naming Conventions
- Indentation: 2 spaces (JS/TS), 4 spaces (Python); UTF‑8; LF line endings; final newline.
- Line length: 100; keep functions short and pure where possible.
- Names: classes `PascalCase`; functions/vars `camelCase` (JS/TS) or `snake_case` (Python);
  files `kebab-case.ext` (JS/TS) or `snake_case.py`.

## Testing Guidelines
- Place tests in `tests/` and mirror `src/` paths.
- Naming: Python `test_*.py`; JS/TS `*.spec.(js|ts)`.
- Aim for ≥80% line coverage where practical; test public behavior over internals.
- Run tests locally before opening a PR.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat(ui): add dark mode toggle`.
- Keep commits scoped and descriptive; avoid mixing unrelated changes.
- PRs include: purpose, summary of changes, linked issues (`Closes #123`), test evidence (logs/screenshots), and notes on breaking changes or migrations.

## Security & Configuration Tips
- Do not commit secrets. Use `.env` and provide `.env.example`.
- Pin dependencies (e.g., `package-lock.json`, `poetry.lock`) and update intentionally.

## Agent‑Specific Instructions
- Scope: entire repository. Prefer minimal, focused diffs; follow existing patterns.
- When adding code, update tests and docs in the same change.
- Do not alter licensing or introduce new tooling without discussion in a PR.


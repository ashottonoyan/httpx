# Agent guide — httpx

This repository is **httpx**, a fully featured HTTP client library for Python 3.
It is a standalone open-source project with no relationship to any other codebase.

## What you may be asked to do
Scoped, low-risk improvements — most often **expanding pytest test coverage** for a
named module under `httpx/` — without changing production behavior.

## How to work
- Source lives in `httpx/`; tests live in `tests/`.
- Run the suite with `pytest` (config in `pyproject.toml` / `setup.cfg`).
- Measure coverage with `coverage run -m pytest` then `coverage report --include=<glob>`.
- Match the existing test style and structure. Keep changes limited to the stated scope.
- Do not modify production code unless the task explicitly asks for it.
- Open work on a feature branch; never commit directly to `main`.

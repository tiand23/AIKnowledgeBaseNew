# Contributing Guide

## 1. Scope

We welcome bug fixes, test improvements, documentation updates, and feature proposals.

## 2. Development Setup

### Backend
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Full stack with Docker (recommended)
```bash
cd app
./start_docker.sh pg up
```

## 3. Branch and Commit

- Create a feature branch from `main`
- Keep commits small and logically grouped
- Use clear commit messages:
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `refactor: ...`
  - `test: ...`

## 4. Pull Request Checklist

Before opening a PR, confirm:
- The change is scoped and explained
- Relevant tests were run
- API/behavior changes are documented
- Screenshots are attached for UI changes
- Security/privacy impact is considered

## 5. Coding Rules

- Keep comments and docstrings in English
- Keep user-facing UI text in Japanese for this project
- Avoid unrelated formatting-only changes in large files
- Do not commit secrets (`.env`, API keys, credentials)

## 6. Issue First for Large Changes

For large features or architecture changes, open an issue first and align on:
- Problem statement
- Proposed approach
- Risks and migration impact

## 7. License

By contributing, you agree that your contributions are provided under the repository license.

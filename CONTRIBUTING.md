# Contributing

## Branching
- `main` is always deployable. Work happens on short-lived branches: `feature/<topic>`, `fix/<topic>`, `docs/<topic>`.
- Open a pull request into `main`; CI (`pytest`) must be green before merging.

## Commit messages (Conventional Commits)
`feat: add waitlist countdown` · `fix: escape % in Postgres SQL` · `test: cover double check-in` · `docs: explain concurrency`

## Local checks before every push
```bash
pip install -r requirements-dev.txt
pytest
```

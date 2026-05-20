# Contributing to ovh-voip-spam-filter

Thanks for considering a contribution! This project is small and pragmatic — PRs welcome on any of the items listed in [`docs/roadmap.md`](docs/roadmap.md), or any bug fix or improvement.

## Development setup

Requirements: **Python 3.12+** and **Docker** (for image-related changes).

```bash
git clone https://github.com/raedkit/ovh-voip-spam-filter.git
cd ovh-voip-spam-filter
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Before opening a PR

Run the full quality suite locally:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest -v
```

If you touched the Dockerfile, verify the image still builds:

```bash
docker build -t ovh-voip-spam-filter:dev .
docker run --rm ovh-voip-spam-filter:dev --help
```

If you touched the docs, preview them locally:

```bash
.venv/bin/pip install ".[docs]"
.venv/bin/mkdocs serve
# open http://127.0.0.1:8000
```

## Branch model

- `main` is the stable branch — anything merged here passes CI and is potentially shippable.
- Feature branches: `feat/<short-description>`
- Bug fixes: `fix/<short-description>`
- Chores / tooling: `chore/<short-description>`
- Docs only: `docs/<short-description>`

## Commit messages

Conventional Commits are **suggested but not required**:

```
feat: add EXTRA_CALL_NUMBERS overlay support
fix: handle 429 without Retry-After header
docs: clarify reconciliation semantics in FR README
chore(deps): bump ruff to 0.12
```

A clear imperative-mood summary line is what matters.

## Pull request checklist

- [ ] Tests cover the change (or explain in the PR description why no test)
- [ ] `ruff check`, `ruff format --check`, `mypy`, `pytest` all pass locally
- [ ] `CHANGELOG.md` updated under the `[Unreleased]` section
- [ ] If a public-facing change, the README/docs reflect it

## Reporting bugs and feature requests

Use the issue templates in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/). Security-sensitive issues should go through [`SECURITY.md`](SECURITY.md) instead.

## Code of conduct

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under [GPL-3.0-or-later](LICENSE).

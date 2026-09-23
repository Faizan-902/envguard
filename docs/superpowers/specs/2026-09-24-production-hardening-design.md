# envguard Production Hardening — Design

Date: 2026-09-24

## Goal

Make `envguard-tools` production-grade while keeping the runtime zero-dependency
brand intact. All tooling added (coverage, mypy) is dev-only and never shipped.

## Scope (5 deliverables)

### 1. Fix validator placeholder logic (`envguard/validator.py`)

**Bug:** rule-level `allow_placeholder=True` is currently ignored when the global
`disallow_placeholders` defaults to `True`, because the guard at the placeholder
check makes `not rule.allow_placeholder` dead for rules that set the flag.

**Fix:** change the condition so that a rule that explicitly sets
`allow_placeholder=True` is never flagged, regardless of the global. The global
value only acts as the default for rules that do not set the flag.

The placeholder check becomes:

```
if val and not rule.allow_placeholder and is_placeholder(val)
```

The global `disallow_placeholders` is used to seed the default of
`allow_placeholder` for rules that do not set it explicitly.

### 2. Expand unit tests (unittest, zero new deps)

- `tests/test_cli.py`: `--dry-run`, `--no-mask`, `--force`, `--no-color`, exit
  codes for missing template (2) and missing env (1), strict pass + fail paths.
- `tests/test_parser.py`: BOM prefix, escaped quotes, multiline edge cases.
- `tests/test_validator.py`: rule-level `allow_placeholder` override (bug
  regression test), custom validator, regex path, float type range checks.
- `tests/test_syncer.py`: target creation when missing, masked vs unmasked init,
  preserve existing values with newlines appended correctly.

### 3. Dev-only quality gates

- `requirements-dev.txt` with `coverage` and `mypy` (referenced by CI only).
- `pyproject.toml` gains `[tool.coverage]` and `[tool.mypy]` sections.
- Package metadata (`dependencies`) stays empty — zero runtime deps preserved.

### 4. CI workflow (`ci.yml`)

- Keep the existing 3-OS × 5-Python test matrix.
- Add jobs:
  - `coverage`: run `coverage run -m unittest discover -s tests`, then
    `coverage report --fail-under=85`.
  - `mypy`: run `mypy envguard` in strict mode.

### 5. Auto-publish workflow (`publish.yml`)

- Trigger: push of a `v*` tag.
- Steps: checkout → setup-python → build wheel + sdist → `twine upload`.
- Needs a `PYPI_TOKEN` repository secret set on GitHub.

### 6. README update

- Add a "Development" section documenting test, coverage, and mypy commands.

## Verification

- `python -m unittest discover -s tests` → all pass.
- `coverage report --fail-under=85` → 85%+.
- `mypy envguard` strict → clean.
- Manual: published wheel still `pip install`s and `envguard --version` works.
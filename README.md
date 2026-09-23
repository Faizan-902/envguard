# EnvGuard

> Audit, validate, and synchronize your environment variables before they break your app.

[![CI](https://github.com/Faizan-902/envguard/actions/workflows/ci.yml/badge.svg)](https://github.com/Faizan-902/envguard/actions)
[![PyPI version](https://img.shields.io/pypi/v/envguard-tools.svg)](https://pypi.org/project/envguard-tools/)
[![Python](https://img.shields.io/pypi/pyversions/envguard-tools.svg)](https://pypi.org/project/envguard-tools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

EnvGuard is a **zero-dependency** CLI and Python library that audits, validates, diffs, and safely synchronizes environment variables across development, staging, and CI/CD pipelines. It catches misconfigured environments **before** your service starts — not hours later in production.

---

## Table of Contents

- [Why EnvGuard?](#why-envguard)
- [Features](#features)
- [Installation](#installation)
- [CLI Usage](#cli-usage)
- [Python SDK](#python-sdk)
- [Configuration Reference](#configuration-reference)
- [CI/CD Integration](#cicd-integration)
- [Exit Codes](#exit-codes)
- [Development](#development)
- [License](#license)

---

## Why EnvGuard?

Environment drift is one of the most common causes of broken local builds and failed deployments:

- Developers add new keys to `.env` but forget to update `.env.example`.
- Teammates pull recent changes and crash because their local `.env` is missing new required keys.
- Placeholders like `API_KEY=<YOUR_KEY_HERE>` or `DEBUG=TODO` slip into production.
- Type errors (e.g. `PORT=foo` instead of an integer) crash services at runtime.

EnvGuard solves these problems **instantly**, with zero external dependencies, readable terminal reports, and CI-ready exit codes.

---

## Features

- **Audit & Validate** — flags missing keys, empty values, and unresolved placeholders in `.env` against `.env.example`.
- **Safe Synchronization** — appends missing keys into `.env` without ever overwriting existing local values.
- **Secret-Safe Templates** — generates `.env.example` from `.env` while automatically masking secrets (`API_KEY`, `PASSWORD`, `JWT_SECRET`, and more).
- **Rich Schema Types** — validates ports, URLs, emails, booleans, integers, floats, JSON, enums, and custom regex.
- **Strict Mode** — fails on undocumented extra variables to keep the environment surface deliberate.
- **CI/CD Ready** — deterministic exit codes (`0`/`1`/`2`), color-free output in non-TTY environments, `NO_COLOR` support.
- **Zero Dependencies** — runs on the Python 3.9+ standard library only.

---

## Installation

```bash
# Install from PyPI
pip install envguard-tools

# Or from source
git clone https://github.com/Faizan-902/envguard.git
cd envguard
pip install -e .
```

Requires **Python 3.9+**. Works on Linux, macOS, and Windows.

---

## CLI Usage

### `check` — Audit your environment

Compare `.env` against the `.env.example` template:

```bash
envguard check
```

Output:

```text
EnvGuard Audit Report
Comparing: .env vs template .env.example

X Missing Variables (1):
  - STRIPE_WEBHOOK_SECRET (defined in .env.example:14)

! Empty or Unresolved Placeholders (1):
  ! DATABASE_URL: placeholder '<YOUR_DB_URL>' (.env:3)

[+] 12 variables valid and populated.

X Environment check failed. Fix issues above before proceeding.
```

Fail on undocumented variables with `--strict`:

```bash
envguard check --strict
```

### `sync` — Synchronize missing variables

Append keys that exist in `.env.example` but are missing from `.env` — existing values are never touched:

```bash
# Preview changes without writing
envguard sync --dry-run

# Synchronize missing keys
envguard sync
```

### `diff` — Compare two environments

Inspect which keys match, are missing, empty, or extra:

```bash
envguard diff -e .env.staging -x .env.production
```

### `init` — Generate a safe `.env.example`

Create a clean template from an existing `.env`, masking sensitive secrets by default:

```bash
envguard init -e .env -o .env.example

# Regenerate even if the template already exists
envguard init -e .env -o .env.example --force

# Keep real values (use with caution)
envguard init -e .env -o .env.example --no-mask
```

---

## Python SDK

Use EnvGuard programmatically in application startup or test suites:

```python
from envguard import EnvValidator, Rule, parse_env_file

# Define schema validation rules
validator = EnvValidator([
    Rule("PORT", type="port", required=True),
    Rule("DEBUG", type="boolean", required=True),
    Rule("DATABASE_URL", type="url", required=True),
    Rule("ENVIRONMENT", type="enum", choices=["development", "staging", "production"]),
    Rule("MAX_CONNECTIONS", type="integer", min_value=1, max_value=100),
])

# Load and validate
env = parse_env_file(".env")
result = validator.validate(env)

if not result.is_valid:
    for issue in result.issues:
        print(f"[{issue.issue_type.upper()}] {issue.message}")
    raise SystemExit(1)

print("Environment configuration is valid.")
```

---

## Configuration Reference

### Global options

| Option            | Description                              |
| ----------------- | ---------------------------------------- |
| `-v, --version`   | Show the installed version.              |
| `--no-color`      | Disable ANSI colored output.             |
| `-h, --help`      | Show help for any command.               |

### `envguard check`

| Option                  | Default         | Description                                        |
| ----------------------- | --------------- | -------------------------------------------------- |
| `-e, --env FILE`        | `.env`          | Target environment file.                           |
| `-x, --example FILE`    | `.env.example`  | Template file to validate against.                 |
| `--strict`              | off             | Fail if the target contains unlisted extra keys.   |

### `envguard sync`

| Option                  | Default         | Description                                        |
| ----------------------- | --------------- | -------------------------------------------------- |
| `-e, --env FILE`        | `.env`          | Target environment file to update.                 |
| `-x, --example FILE`    | `.env.example`  | Template file that defines the source of truth.    |
| `--empty`               | off             | Add keys with empty values instead of defaults.    |
| `--dry-run`             | off             | Preview missing keys without writing anything.     |

### `envguard diff`

| Option                  | Default         | Description                                        |
| ----------------------- | --------------- | -------------------------------------------------- |
| `-e, --env FILE`        | `.env`          | Target environment file.                           |
| `-x, --example FILE`    | `.env.example`  | Comparison baseline.                               |

### `envguard init`

| Option                  | Default         | Description                                        |
| ----------------------- | --------------- | -------------------------------------------------- |
| `-e, --env FILE`        | `.env`          | Source environment file.                           |
| `-o, --out FILE`        | `.env.example`  | Output template path.                              |
| `-f, --force`           | off             | Overwrite the output file if it already exists.    |
| `--no-mask`             | off             | Do not mask sensitive keys with placeholders.      |

---

## CI/CD Integration

Block PRs and deployments with missing or invalid environment variables. In GitHub Actions:

```yaml
- name: Verify Environment Variables
  run: |
    pip install envguard-tools
    envguard check --strict
```

In any CI/CD pipeline:

```bash
pip install envguard-tools
envguard check -e .env.ci -x .env.example
envguard sync --dry-run
```

---

## Exit Codes

EnvGuard returns deterministic status codes so your CI can act on the result:

| Code | Meaning                                              |
| ---- | ---------------------------------------------------- |
| `0`  | Environment is healthy and in sync.                  |
| `1`  | Missing, empty, or invalid variables were found.     |
| `2`  | Syntax errors or missing files were encountered.     |

---

## Development

Set up a development environment:

```bash
git clone https://github.com/Faizan-902/envguard.git
cd envguard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Measure coverage (gated at ≥85% in CI):

```bash
coverage run -m unittest discover -s tests
coverage report
```

Type-check with strict mypy:

```bash
mypy envguard
```

Build and verify the distribution locally:

```bash
python -m build
twine check dist/*
```

Publish a new release to PyPI:

```bash
python -m build
twine upload dist/*
```

> Releasing via GitHub: pushing a `v*` tag (e.g. `v0.1.2`) automatically runs the test matrix, coverage, and type checks, then publishes to PyPI.

---

## License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 Faizan.
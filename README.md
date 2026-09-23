# EnvGuard

[![CI](https://github.com/Faizan-902/envguard/actions/workflows/ci.yml/badge.svg)](https://github.com/Faizan-902/envguard/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

A zero-dependency, developer-friendly CLI and Python library to audit, validate, diff, and safely synchronize environment variables across development, staging, and CI/CD pipelines.

---

## Why EnvGuard?

Environment drift is one of the most frequent causes of broken local builds and failed production deployments:
- Developers add new keys in `.env` but forget to update `.env.example`.
- Team members pull recent changes and crash because their local `.env` is missing new required keys.
- Placeholders like `API_KEY=<YOUR_KEY_HERE>` or `DEBUG=TODO` accidentally get deployed.
- Incorrect types (e.g. `PORT=foo` instead of a valid integer) crash services at runtime.

**EnvGuard solves this instantly** with zero external dependencies, human-friendly colorized terminal reports, and CI-ready exit codes.

---

## Features

- **Automatic Audit & Validation**: Compares `.env` with `.env.example` to detect missing keys, unpopulated secrets, and dummy placeholders.
- **Safe Synchronization**: Automatically syncs missing keys into your `.env` without overwriting existing local values.
- **Secret-Safe Template Generation**: Creates `.env.example` from your `.env`, automatically masking sensitive secrets (`API_KEY`, `PASSWORD`, `JWT_SECRET`, etc.).
- **Rich Schema Types**: Validate types, ports (1-65535), URLs, emails, JSON strings, enums, numbers, and custom regex.
- **CI/CD Ready**: Exits with deterministic status codes (`0` for success, `1` for missing/invalid keys, `2` for syntax/file errors).
- **Zero External Dependencies**: Runs on standard Python 3.9+ standard library.

---

## Installation

```bash
# Install locally in editable mode
pip install -e .

# Or install directly with pip
pip install envguard-tools
```

---

## CLI Usage

### 1. Audit Environment (`check`)
Check if `.env` has all variables defined in `.env.example` and contains no unresolved placeholders:

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

### 2. Synchronize Missing Variables (`sync`)
Automatically append missing keys from `.env.example` to your `.env` without modifying existing values:

```bash
# Preview changes without writing
envguard sync --dry-run

# Synchronize missing keys
envguard sync
```

### 3. Compare Environments (`diff`)
View a breakdown of matching, missing, extra, and placeholder variables:

```bash
envguard diff -e .env.staging -x .env.production
```

### 4. Generate Safe `.env.example` (`init`)
Generate a clean template from an existing `.env` with all sensitive credentials automatically masked:

```bash
envguard init -e .env -o .env.example
```

---

## Python SDK Usage

You can also use EnvGuard programmatically in your application startup or test suites:

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
```

---

## CI/CD Integration

Add EnvGuard to your GitHub Actions workflow to block PRs with missing environment variables:

```yaml
- name: Verify Environment Variables
  run: |
    pip install envguard-tools
    envguard check --strict
```

---

## Running Tests

Run the full test suite across all modules:

```bash
python -m unittest discover -s tests -v
```

---

## License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 Faizan.

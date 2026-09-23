# envguard Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden `envguard-tools` for production: fix the validator placeholder bug, expand test coverage to ≥85%, add mypy + coverage CI gates, and add automatic PyPI publishing.

**Architecture:** Keep zero runtime deps. Fix `validator.py` placeholder precedence, expand `unittest` tests, add dev-only `requirements-dev.txt` (coverage, mypy), extend `ci.yml` with hardening jobs, add `publish.yml`, update README.

**Tech Stack:** Python 3.9+, `unittest`, `coverage`, `mypy`, GitHub Actions, `build`/`twine` for publishing.

---

### Task 1: Fix validator placeholder logic + regression test

**Files:**
- Modify: `envguard/validator.py:47-49,84`
- Test: `tests/test_validator.py`

- [ ] **Step 1: Write the failing regression test**

Append to `tests/test_validator.py`:

```python
    def test_rule_allow_placeholder_overrides_global(self):
        validator = EnvValidator([
            Rule("API_KEY", allow_placeholder=True),
        ])
        env = parse_env_content("API_KEY=<YOUR_KEY_HERE>")
        res = validator.validate(env)
        self.assertTrue(res.is_valid)

    def test_rule_placeholder_flagged_without_override(self):
        validator = EnvValidator([
            Rule("API_KEY", allow_placeholder=False),
        ])
        env = parse_env_content("API_KEY=<YOUR_KEY_HERE>")
        res = validator.validate(env)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.issues[0].issue_type, "placeholder")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_validator.TestEnvValidator.test_rule_allow_placeholder_overrides_global -v`
Expected: FAIL (first test) — placeholder is flagged despite `allow_placeholder=True`.

- [ ] **Step 3: Implement the fix in `envguard/validator.py`**

Change the placeholder check at line ~84 to make the rule flag authoritative:

```python
            if val and not rule.allow_placeholder:
                if is_placeholder(val):
                    issues.append(ValidationIssue(
                        key=key,
                        issue_type="placeholder",
                        message=f"Variable '{key}' contains unresolved placeholder: '{val}'",
                        line_number=entry.line_number,
                    ))
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m unittest discover -s tests`
Expected: OK, 21+ tests passing.

- [ ] **Step 5: Commit**

```bash
git add envguard/validator.py tests/test_validator.py
git commit -m "fix: respect rule-level allow_placeholder override"
```

---

### Task 2: Expand CLI tests

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add missing CLI path tests**

Append to `tests/test_cli.py` (imports `subprocess` stays unnecessary; use `argparse.Namespace` and `mock.patch` where needed):

```python
    def test_cmd_check_missing_template_returns_2(self):
        tmpl = self.base / "nope.example"
        env = self.base / ".env"
        env.write_text("A=1\n", encoding="utf-8")
        args = argparse.Namespace(env=str(env), example=str(tmpl), strict=False)
        self.assertEqual(cmd_check(args), 2)

    def test_cmd_check_missing_env_returns_1(self):
        tmpl = self.base / ".env.example"
        tmpl.write_text("A=1\n", encoding="utf-8")
        args = argparse.Namespace(env=str(self.base / "gone.env"), example=str(tmpl), strict=False)
        self.assertEqual(cmd_check(args), 1)

    def test_cmd_check_strict_extra_vars_fail(self):
        tmpl = self.base / ".env.example"
        env = self.base / ".env"
        tmpl.write_text("PORT=3000\n", encoding="utf-8")
        env.write_text("PORT=3000\nEXTRA=1\n", encoding="utf-8")
        args = argparse.Namespace(env=str(env), example=str(tmpl), strict=True)
        self.assertEqual(cmd_check(args), 1)

    def test_cmd_check_strict_clean_returns_0(self):
        tmpl = self.base / ".env.example"
        env = self.base / ".env"
        tmpl.write_text("PORT=3000\n", encoding="utf-8")
        env.write_text("PORT=3000\n", encoding="utf-8")
        args = argparse.Namespace(env=str(env), example=str(tmpl), strict=True)
        self.assertEqual(cmd_check(args), 0)

    def test_cmd_init_force_overwrites(self):
        env = self.base / "real.env"
        tmpl = self.base / "out.example"
        env.write_text("PORT=1\n", encoding="utf-8")
        tmpl.write_text("OLD=1\n", encoding="utf-8")
        args = argparse.Namespace(env=str(env), out=str(tmpl), force=True, no_mask=False)
        self.assertEqual(cmd_init(args), 0)
        self.assertNotIn("OLD", tmpl.read_text(encoding="utf-8"))

    def test_cmd_init_no_mask_keeps_secrets(self):
        env = self.base / "real.env"
        tmpl = self.base / "out.example"
        env.write_text("JWT_SECRET=super_secret\n", encoding="utf-8")
        args = argparse.Namespace(env=str(env), out=str(tmpl), force=True, no_mask=True)
        self.assertEqual(cmd_init(args), 0)
        self.assertIn("JWT_SECRET=super_secret", tmpl.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run the tests**

Run: `.venv/bin/python -m unittest tests.test_cli -v`
Expected: all pass (PASS) — includes existing 4 + new 6.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: cover CLI missing-file, strict, and init paths"
```

---

### Task 3: Expand parser + validator + syncer tests

**Files:**
- Modify: `tests/test_parser.py`, `tests/test_validator.py`, `tests/test_syncer.py`

- [ ] **Step 1: Add parser edge case tests**

Append to `tests/test_parser.py`:

```python
    def test_bom_prefix(self):
        content = "\ufeffPORT=8080\nHOST=localhost"
        env = parse_env_content(content)
        self.assertEqual(env.get("PORT"), "8080")
        self.assertEqual(env.get("HOST"), "localhost")

    def test_escaped_quotes_in_double_quoted(self):
        content = 'MSG="say \\"hi\\" now"'
        env = parse_env_content(content)
        self.assertEqual(env.get("MSG"), 'say "hi" now')

    def test_equals_in_unquoted_value(self):
        content = "PLAN=A=B=C"
        env = parse_env_content(content)
        self.assertEqual(env.get("PLAN"), "A=B=C")
```

- [ ] **Step 2: Add validator type tests**

Append to `tests/test_validator.py`:

```python
    def test_float_range_validation(self):
        validator = EnvValidator([
            Rule("RATIO", type="float", min_value=0.0, max_value=1.0),
        ])
        self.assertTrue(validator.validate(parse_env_content("RATIO=0.5")).is_valid)
        self.assertFalse(validator.validate(parse_env_content("RATIO=2.5")).is_valid)

    def test_regex_validation(self):
        validator = EnvValidator([
            Rule("CODE", type="string", regex=r"^[A-Z]{3}-\d{2}$"),
        ])
        self.assertTrue(validator.validate(parse_env_content("CODE=ABC-12")).is_valid)
        self.assertFalse(validator.validate(parse_env_content("CODE=ab-12")).is_valid)

    def test_custom_validator_error_string(self):
        def always_bad(val):
            return "custom check failed"
        validator = EnvValidator([
            Rule("X", custom_validator=always_bad),
        ])
        res = validator.validate(parse_env_content("X=anything"))
        self.assertFalse(res.is_valid)
        self.assertIn("custom check failed", res.issues[0].message)

    def test_json_type_validation(self):
        validator = EnvValidator([
            Rule("CFG", type="json"),
        ])
        self.assertTrue(validator.validate(parse_env_content('CFG={"a": 1}')).is_valid)
        self.assertFalse(validator.validate(parse_env_content("CFG=not-json")).is_valid)
```

- [ ] **Step 3: Add syncer tests**

Append to `tests/test_syncer.py`:

```python
    def test_sync_creates_missing_target_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("PORT=3000\n", encoding="utf-8")
            updated, added = sync_env_files(tmpl_file, target_file)
            self.assertTrue(updated)
            self.assertEqual(added, ["PORT"])
            self.assertIn("PORT=3000", target_file.read_text(encoding="utf-8"))

    def test_generate_example_no_mask(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text("JWT_SECRET=super_secret\n", encoding="utf-8")
            template = generate_example_template(src, mask_secrets=False)
            self.assertIn("JWT_SECRET=super_secret", template)

    def test_sync_preserves_existing_and_appends_newline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            target_file.write_text("A=1", encoding="utf-8")
            updated, added = sync_env_files(tmpl_file, target_file)
            self.assertEqual(added, ["B"])
            content = target_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            self.assertEqual(lines[0], "A=1")
            self.assertIn("B=2", content)
```

- [ ] **Step 4: Run full suite**

Run: `.venv/bin/python -m unittest discover -s tests`
Expected: OK, ~31 tests.

- [ ] **Step 5: Commit**

```bash
git add tests/ tests/
git commit -m "test: cover BOM, escaped quotes, types, and sync edge cases"
```

---

### Task 4: Dev-only quality gates config

**Files:**
- Create: `requirements-dev.txt`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create `requirements-dev.txt`**

```text
coverage>=7.0
mypy>=1.8
build>=1.0
twine>=5.0
```

- [ ] **Step 2: Add tool configs to `pyproject.toml`**

Append:

```toml
[tool.coverage.run]
source = ["envguard"]
branch = true

[tool.coverage.report]
fail_under = 85
show_missing = true

[tool.mypy]
python_version = "3.9"
strict = true
```

- [ ] **Step 3: Commit**

```bash
git add requirements-dev.txt pyproject.toml
git commit -m "chore: add dev-only coverage and mypy configs"
```

---

### Task 5: Add CI hardening jobs

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add coverage + mypy jobs**

Append to `.github/workflows/ci.yml`:

```yaml
  coverage:
    name: Coverage
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: coverage run -m unittest discover -s tests
      - run: coverage report --fail-under=85

  mypy:
    name: Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: mypy envguard
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add coverage and mypy gates"
```

---

### Task 6: Add auto-publish workflow

**Files:**
- Create: `.github/workflows/publish.yml`

- [ ] **Step 1: Write `publish.yml`**

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

permissions:
  contents: read

jobs:
  publish:
    name: Build and publish
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - name: Upload to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: twine upload --skip-existing dist/*
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: auto-publish to PyPI on version tags"
```

---

### Task 7: README development section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Development section after "Running Tests"**

Replace the `## Running Tests` heading block with:

```markdown
## Development

Run the full test suite:

```bash
python -m unittest discover -s tests -v
```

Measure coverage (must stay ≥85%):

```bash
pip install -r requirements-dev.txt
coverage run -m unittest discover -s tests
coverage report
```

Type-check:

```bash
mypy envguard
```

Publish a new release:

```bash
pip install -r requirements-dev.txt
python -m build
twine upload dist/*
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document dev test, coverage, and publish workflow"
```

---

### Task 8: Final verification

**Files:** none

- [ ] **Step 1: Run full verification locally**

Run:
```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m coverage run -m unittest discover -s tests && .venv/bin/python -m coverage report --fail-under=85
.venv/bin/python -m mypy envguard
```
Expected: all pass; coverage report ≥85%; mypy exit 0.

- [ ] **Step 2: Push to GitHub**

```bash
git push origin main
```

- [ ] **Step 3: Verify GitHub CI green**

Expected: `CI` workflow (test matrix + coverage + mypy) all complete/success.
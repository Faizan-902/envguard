# EnvGuard Correctness & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the parser, CLI error contract, template-masking, and write-safety defects found by auditing `envguard` 0.1.1, then ship 0.2.0 to GitHub with tests proving each fix.

**Status:** implemented. The 0.1.2 draft became 0.2.0 because quoted-value decoding and `#` handling change parsed output for existing files.

**Architecture:** Keep zero runtime dependencies and the existing module layout. `parser.py` owns quoting/escaping, `syncer.py` owns diffing/masking/file writes, `cli.py` owns the exit-code contract. Every fix starts with a failing regression test.

**Tech Stack:** Python 3.9+, `unittest`, `coverage` (≥85 gate), strict `mypy`, GitHub Actions.

## Global Constraints

- Zero runtime dependencies (`dependencies = []` must stay).
- Public API in `envguard/__init__.py` may only grow, never break.
- Exit-code contract: `0` healthy, `1` missing/empty/invalid variables, `2` syntax error or unusable file.
- Python floor stays `>=3.9`; every new construct must run on 3.9.
- Test style stays `unittest.TestCase`; run with `python -m unittest discover -s tests`.

## Findings (evidence)

| ID | Severity | Defect | Evidence |
| --- | --- | --- | --- |
| F1 | Critical | Double-quoted values are decoded with `value.encode().decode("unicode_escape")`, which raises `UnicodeDecodeError` on `\U`, `\x`, `\N` sequences. Any Windows path in a `.env` crashes the tool with a traceback. | `parse_env_content(r'PATH="C:\Users\dev\bin"')` → `UnicodeDecodeError: truncated \UXXXXXXXX escape` |
| F2 | High | The same decode mojibakes non-ASCII: UTF-8 bytes are reinterpreted as latin-1. | `NAME="café"` → `cafÃ©`; `PATH="C:\new\table"` → real newline + TAB |
| F3 | High | Unquoted values treat `#` as a comment start even without preceding whitespace, truncating legitimate values. | `PASSWORD=abc#123` → `abc` |
| F4 | High (security) | `init` masks by key name only, so `DATABASE_URL=postgres://user:pass@host/db` is written verbatim into `.env.example`, which is normally committed. | `generate_example_template()` leaks the DSN |
| F5 | Medium | `diff`, `sync --dry-run`, and `init` let `ParseError`/`OSError` escape as a traceback with exit 1, contradicting the documented exit 2. | `envguard diff` on `BAD KEY=1` → traceback, exit 1 |
| F6 | Medium (data safety) | `sync`/`init` rewrite user files with `Path.write_text`, truncating in place; an interrupt leaves a half-written `.env`. | code read |
| F7 | Medium (release) | `publish.yml` uploads to PyPI without running the test suite (`ci.yml` only triggers on branches). | workflow read |
| F8 | Medium (security) | `.gitignore` ignores only `.env` and `.env.local`; `.env.production` / `.env.staging` in a secret-management repo are committable. | `.gitignore` read |
| F9 | Low | Unused imports in `cli.py`; `sync` can emit a double blank line; version duplicated between `pyproject.toml` and `__version__`; no `py.typed` despite strict typing; CI matrix stops at 3.13; README exit-code table contradicts behaviour. | code read |

**Post-review additions (found by independent review of the first pass):** empty-user and `jdbc:` DSNs were still unmasked; `cred` narrowing leaked `*_CREDS`; single-quoted `'C:\'` was rejected; non-UTF-8 files were silently replaced instead of rejected; `init`/`sync` wrote parsed values back unquoted, destroying multiline values and values starting with `#`; CRLF files were converted to LF; `.gitignore` hid non-`.example` templates.

## Review Focus

- A `.env` written on Windows (backslash paths, CRLF) must round-trip without corruption — owned by Task 1.
- A value containing `#`, spaces, or quotes must survive `check`/`sync` intact — Task 1.
- An existing `.env` must never be destroyed by a failed `sync` — Task 4.
- A template produced by `init` must never contain a live credential — Task 2.
- A malformed file must always produce a clean message and exit 2, never a traceback — Task 3.

---

### Task 1: Safe escape decoding and comment rules in the parser

**Files:**
- Modify: `envguard/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Produces: `_decode_double_quoted(text: str) -> str`, `_find_unescaped(text: str, quote_char: str, start: int = 0) -> int` (internal).
- Unchanged: `parse_env_content(content: str, path: str = "<string>") -> EnvFile`, `parse_env_file(file_path) -> EnvFile`.

- [ ] **Step 1: Write failing tests** for: literal Windows path stays intact, non-ASCII value stays intact, `\n`/`\t` still decode, unknown escape stays literal, `abc#123` is not truncated, `KEY= # comment` is empty, multiline escaped quote does not close early.
- [ ] **Step 2: Run** `python -m unittest tests.test_parser -v`; expect failures/crash.
- [ ] **Step 3: Implement** a manual escape decoder that unescapes only `\\`, `\"`, and `\'`, preserving every other backslash pair literally so Windows paths survive; use it for single-line and multiline double-quoted values. Single-quoted values are literal (no escape processing). Treat `#` as an inline comment only at index 0 or after whitespace. Scan for the closing quote with escape awareness in multiline values, and reject non-UTF-8 files with a `ParseError`.
- [ ] **Step 4: Run** the parser tests, then the full suite.
- [ ] **Step 5: Commit.**

### Task 2: Credential-aware masking in `init`

**Files:**
- Modify: `envguard/syncer.py`
- Test: `tests/test_syncer.py`

**Interfaces:**
- Produces: `_is_sensitive(key: str, value: str) -> bool` (internal).
- Unchanged: `generate_example_template(source_env_path, output_path=None, mask_secrets=True) -> str`.

- [ ] **Step 1: Write failing tests**: `DATABASE_URL=postgres://user:pass@host/db` is masked; `REDIS_URL` with credentials is masked; `APP_URL=https://example.com` is not masked; key-name matches (`JWT_SECRET`) still masked; `mask_secrets=False` still keeps values.
- [ ] **Step 2: Run** the tests; expect failure.
- [ ] **Step 3: Implement** `_is_sensitive` = key pattern match OR `scheme://user:pass@` value match; mask with `<YOUR_{KEY}_HERE>`.
- [ ] **Step 4: Run** `tests/test_syncer.py` and the full suite.
- [ ] **Step 5: Commit.**

### Task 3: CLI never leaks a traceback

**Files:**
- Modify: `envguard/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `_report_error(err: BaseException) -> int` returning `2`.
- Unchanged: `cmd_check/cmd_diff/cmd_sync/cmd_init(args) -> int`, `main() -> None`.

- [ ] **Step 1: Write failing tests** driving `main()` with mocked `sys.argv` for: `diff` on `BAD KEY=1`, `sync` on a malformed target, `init` on a malformed source, `check` on an unreadable path. Assert `SystemExit.code == 2` and no traceback text.
- [ ] **Step 2: Run** the tests; expect tracebacks.
- [ ] **Step 3: Implement** `_report_error`, wrap the parse/IO work in every handler, and add a `(EnvGuardError, OSError)` backstop around dispatch in `main`.
- [ ] **Step 4: Run** `tests/test_cli.py` and the full suite.
- [ ] **Step 5: Commit.**

### Task 4: Atomic writes and clean sync output

**Files:**
- Modify: `envguard/syncer.py`
- Test: `tests/test_syncer.py`

**Interfaces:**
- Produces: `_atomic_write_text(path: Path, text: str) -> None` (internal).
- Unchanged: `sync_env_files(template_path, target_path, fill_defaults=True) -> tuple[bool, list[str]]`.

- [ ] **Step 1: Write failing tests**: target file mode preserved; no `.tmp` residue after success; appending to a file without trailing newline yields exactly one blank separator line; a write failure leaves the original bytes intact (patch `os.replace` to raise).
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Implement** `_atomic_write_text` (temp file in the target directory, fsync, `shutil.copymode` when replacing, `os.replace`, cleanup on failure) and use it in `sync_env_files` + `generate_example_template`; fix the newline join.
- [ ] **Step 4: Run** the full suite.
- [ ] **Step 5: Commit.**

### Task 5: Packaging, CI, and docs

**Files:**
- Create: `envguard/py.typed`
- Modify: `pyproject.toml`, `.github/workflows/publish.yml`, `.github/workflows/ci.yml`, `.gitignore`, `README.md`
- Test: `tests/test_packaging.py`

**Interfaces:**
- Produces: version-consistency test between `pyproject.toml` and `envguard.__version__`.

- [ ] **Step 1: Write the failing test** (`tests/test_packaging.py`) reading `pyproject.toml` with a regex and asserting equality with `__version__`.
- [ ] **Step 2: Run**; expect failure after the bump is applied (proves the guard works).
- [ ] **Step 3: Implement** version `0.2.0`, `py.typed` + package-data, Python 3.9–3.14 matrix and classifiers, a test + tag/version gate in `publish.yml`, `.env*` ignore rules that keep `.env.example`, `.env.sample`, `.env.template`, and `.env.dist` committable, README exit-code/escaping/masking corrections.
- [ ] **Step 4: Run** full suite, coverage, mypy, `python -m build`, `twine check dist/*`.
- [ ] **Step 5: Commit.**

### Task 6: Verify and publish

- [ ] **Step 1:** `python -m unittest discover -s tests -v` on 3.13 and 3.14 → all pass.
- [ ] **Step 2:** `coverage report` → ≥85%, `mypy envguard` → clean.
- [ ] **Step 3:** Build wheel/sdist, install the wheel into a clean venv, run `envguard --version` and a real check/sync cycle against a Windows-path `.env`.
- [ ] **Step 4:** Push `main` to `origin`, confirm the GitHub Actions run is green.

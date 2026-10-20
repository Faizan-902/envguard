# Changelog

All notable changes to `envguard-tools` are documented here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-21

Correctness and hardening release. Two parsing changes alter the value EnvGuard
reports for some existing files — see "Changed" below before upgrading in CI.

### Fixed

- **Crash on Windows paths.** Double-quoted values were decoded with
  `bytes.decode("unicode_escape")`, which raised `UnicodeDecodeError` for any
  `\U`, `\x`, or `\N` sequence (`PATH="C:\Users\dev"`). Only `\\`, `\"`, and `\'`
  are unescaped now; every other backslash is preserved literally.
- **Mojibake.** The same decode turned UTF-8 values into latin-1 (`café` →
  `cafÃ©`). Non-ASCII values are now preserved exactly.
- **Truncated values.** An unquoted `#` was treated as a comment start, so
  `PASSWORD=abc#123` became `abc`. A comment now requires a preceding
  whitespace character, matching `python-dotenv`.
- **Credential leaks in generated templates.** `init` masked only by key name,
  so `DATABASE_URL=postgres://user:pass@host/db` was written verbatim into
  `.env.example`. Values containing `://user:pass@` are masked too, including
  empty-user (`redis://:pass@host`), prefixed-scheme (`jdbc:postgresql://…`),
  and passwords containing `/`. `*_CREDS`, `*_PAT`, `*_SK`, and `*_WEBHOOK*`
  keys are masked as well.
- **Silent merge of keys.** A quoted value that never closed could swallow the
  following assignment. Content after a closing quote is now a syntax error.
- **Tracebacks instead of exit codes.** `diff`, `sync --dry-run`, and `init`
  raised `ParseError` as a traceback with exit `1`. Every command now reports a
  one-line error and returns `2`.
- **Data loss on interrupted writes.** `sync` and `init` rewrote files in place;
  an interrupt could truncate `.env`. Writes go through a temporary file,
  `fsync`, and `os.replace`, preserving mode, symlinks, line endings, and BOM.
- **Corrupting non-UTF-8 files.** Undecodable files are rejected with exit `2`
  instead of being rewritten with replacement characters.
- **Lost quoting on write-back.** `init`/`sync` emitted parsed values unquoted,
  destroying multiline values and values beginning with `#`. Values are now
  re-quoted when needed and round-trip unchanged.
- **Untested PyPI releases.** A `v*` tag did not run CI. Publishing now runs the
  test suite, verifies the tag matches the package version, and runs
  `twine check` before uploading.

### Added

- `envguard/py.typed` — the package ships PEP 561 type information.
- Python 3.14 in the CI matrix and in the classifiers.
- A packaging test that keeps `pyproject.toml` and `envguard.__version__` in sync.

### Changed

- `KEY="line1\nline2"` now yields a literal backslash-n. Real newlines inside
  double quotes still produce multi-line values, and unquoted values are
  unaffected.
- Single-quoted values are fully literal, so `KEY='C:\'` closes normally.
- `.env.production`, `.env.staging`, and every other `.env.*` variant are
  git-ignored; `.env.example`, `.env.sample`, `.env.template`, and `.env.dist`
  remain committable.
- License metadata uses a PEP 639 SPDX expression and builds require
  `setuptools>=77.0.3`.

## [0.1.1] - 2026-09-23

- Fix `allow_placeholder` precedence, expand tests, add coverage/mypy gates and
  tagged PyPI publishing, rewrite the README.

## [0.1.0] - 2026-08-23

- Initial release: `check`, `diff`, `sync`, and `init` commands plus the
  `EnvValidator` schema API.

[0.2.0]: https://github.com/Faizan-902/envguard/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Faizan-902/envguard/releases/tag/v0.1.1

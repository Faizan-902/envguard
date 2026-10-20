from __future__ import annotations

import contextlib
import os
import re
import shutil
import tempfile
from pathlib import Path
from .models import DiffResult, EnvFile
from .parser import parse_env_file
from .exceptions import ParseError
from .validator import is_placeholder

_SENSITIVE_KEY_RE = re.compile(
    r"(?:secret|token|password|pass|pwd|key|auth|cred|private|salt|dsn|jwt|cookie|session|signature|webhook"
    r"|(?:^|_)pat(?:$|_)|(?:^|_)sk(?:$|_))",
    re.IGNORECASE,
)

#: ``scheme://user:password@host`` anywhere in the value. The userinfo may be
#: empty (``redis://:pass@host``) and may itself contain ``/``, and the scheme may
#: be prefixed (``jdbc:postgresql://user:pass@host``) - the value is a credential
#: even when the key name (``DATABASE_URL``) gives nothing away.
_CREDENTIAL_URL_RE = re.compile(r"://[^\s@]*:[^\s@]+@")

#: Values that cannot be written back verbatim without changing meaning.
_VALUE_NEEDS_QUOTES_RE = re.compile(r"(^\s|\s$|#|\n|\r|^[\"'])")


def _is_sensitive(key: str, value: str) -> bool:
    """Return True when either the key name or the value looks like a credential."""
    return bool(_SENSITIVE_KEY_RE.search(key)) or bool(_CREDENTIAL_URL_RE.search(value))


def _format_value(value: str) -> str:
    """Render ``value`` so that parsing it again yields the identical string."""
    if not value:
        return ""
    if not _VALUE_NEEDS_QUOTES_RE.search(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _atomic_write_text(path: Path, text: str, new_file_mode: int = 0o644) -> None:
    """Write ``text`` to ``path`` without ever leaving a partially written file.

    The content goes to a temporary file in the same directory which is then
    swapped into place, so an interrupted run cannot truncate the user's ``.env``.
    The permission bits of an existing file are preserved; a new file is created
    with ``new_file_mode``. Symlinks are followed so dotfile-managed ``.env``
    links keep pointing at the file that was actually updated.
    """
    if path.is_symlink():
        path = path.resolve()

    if not path.parent.exists():
        raise FileNotFoundError(f"Directory '{path.parent}' does not exist")

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copymode(path, tmp_name)
        else:
            os.chmod(tmp_name, new_file_mode)
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def compare_env_files(template: EnvFile, target: EnvFile) -> DiffResult:
    diff = DiffResult()

    template_keys = set(template.entries.keys())
    target_keys = set(target.entries.keys())

    for key in template_keys:
        if key not in target_keys:
            diff.missing_in_target.append(key)
        else:
            val = target.entries[key].value
            if not val or is_placeholder(val):
                diff.empty_in_target.append(key)
            else:
                diff.matching_keys.append(key)

    for key in target_keys:
        if key not in template_keys:
            diff.extra_in_target.append(key)

    diff.missing_in_target.sort()
    diff.extra_in_target.sort()
    diff.empty_in_target.sort()
    diff.matching_keys.sort()

    return diff


def sync_env_files(
    template_path: str | Path,
    target_path: str | Path,
    fill_defaults: bool = True,
) -> tuple[bool, list[str]]:
    tmpl = parse_env_file(template_path)
    target = parse_env_file(target_path) if Path(target_path).exists() else EnvFile(path=str(target_path))

    diff = compare_env_files(tmpl, target)
    if not diff.missing_in_target:
        return False, []

    p = Path(target_path)
    raw = p.read_bytes() if p.exists() else b""
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        # Normalise to LF while composing, then restore the file's own line endings.
        current_content = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as err:
        # Defence in depth: parse_env_file has already rejected this file, but the
        # writer must also refuse to touch content it cannot round-trip.
        raise ParseError(
            f"'{p}' is not valid UTF-8 ({err.reason} at byte {err.start}); refusing to modify it"
        ) from err
    line_ending = "\r\n" if b"\r\n" in raw else "\n"

    lines_to_add: list[str] = []
    for key in diff.missing_in_target:
        tmpl_entry = tmpl.entries[key]
        default_val = _format_value(tmpl_entry.value) if fill_defaults else ""
        comment_part = f" # {tmpl_entry.comment}" if tmpl_entry.comment else ""
        export_prefix = "export " if tmpl_entry.is_exported else ""
        lines_to_add.append(f"{export_prefix}{key}={default_val}{comment_part}")

    prefix = ""
    if current_content:
        prefix = current_content if current_content.endswith("\n") else current_content + "\n"
        prefix += "\n"

    new_content = prefix + "\n".join(["# --- Added by envguard sync ---", *lines_to_add]) + "\n"
    if line_ending != "\n":
        new_content = new_content.replace("\n", line_ending)
    if has_bom:
        new_content = "\ufeff" + new_content
    _atomic_write_text(p, new_content, new_file_mode=0o600)

    return True, diff.missing_in_target


def generate_example_template(
    source_env_path: str | Path,
    output_path: str | Path | None = None,
    mask_secrets: bool = True,
) -> str:
    src = parse_env_file(source_env_path)
    lines: list[str] = []

    for entry in src:
        key = entry.key
        val = entry.value
        comment = f" # {entry.comment}" if entry.comment else ""
        export_prefix = "export " if entry.is_exported else ""

        if mask_secrets and _is_sensitive(key, val):
            masked_val = f"<YOUR_{key.upper()}_HERE>"
            lines.append(f"{export_prefix}{key}={masked_val}{comment}")
        else:
            lines.append(f"{export_prefix}{key}={_format_value(val)}{comment}")

    result_text = "\n".join(lines) + "\n"

    if output_path:
        _atomic_write_text(Path(output_path), result_text)

    return result_text

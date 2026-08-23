from __future__ import annotations

import re
from pathlib import Path
from .models import DiffResult, EnvFile
from .parser import parse_env_file, parse_env_content
from .validator import is_placeholder

_SENSITIVE_KEY_RE = re.compile(
    r"(?:secret|token|password|pass|key|auth|cred|private|salt|dsn|jwt)",
    re.IGNORECASE,
)


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
    current_content = p.read_text(encoding="utf-8") if p.exists() else ""

    lines_to_add: list[str] = []
    if current_content and not current_content.endswith("\n"):
        lines_to_add.append("\n")

    lines_to_add.append("\n# --- Added by envguard sync ---")
    for key in diff.missing_in_target:
        tmpl_entry = tmpl.entries[key]
        default_val = tmpl_entry.value if fill_defaults else ""
        comment_part = f" # {tmpl_entry.comment}" if tmpl_entry.comment else ""
        export_prefix = "export " if tmpl_entry.is_exported else ""
        lines_to_add.append(f"{export_prefix}{key}={default_val}{comment_part}")

    new_content = current_content + "\n".join(lines_to_add) + "\n"
    p.write_text(new_content, encoding="utf-8")

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

        if mask_secrets and _SENSITIVE_KEY_RE.search(key):
            masked_val = f"<YOUR_{key.upper()}_HERE>"
            lines.append(f"{export_prefix}{key}={masked_val}{comment}")
        else:
            lines.append(f"{export_prefix}{key}={val}{comment}")

    result_text = "\n".join(lines) + "\n"

    if output_path:
        Path(output_path).write_text(result_text, encoding="utf-8")

    return result_text

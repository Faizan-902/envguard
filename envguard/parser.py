from __future__ import annotations

import re
from pathlib import Path
from .exceptions import ParseError
from .models import EnvEntry, EnvFile

_EXPORT_PREFIX_RE = re.compile(r"^\s*export\s+")
_KEY_VAL_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", re.DOTALL)


def _strip_quotes_and_comment(raw_val: str) -> tuple[str, str | None]:
    val = raw_val.strip()
    if not val:
        return "", None

    if val.startswith('"'):
        end_idx = _find_matching_quote(val, '"')
        if end_idx != -1:
            extracted = val[1:end_idx].encode().decode("unicode_escape")
            remainder = val[end_idx + 1:].strip()
            comment = remainder.lstrip('#').strip() if remainder.startswith('#') else None
            return extracted, comment

    if val.startswith("'"):
        end_idx = _find_matching_quote(val, "'")
        if end_idx != -1:
            extracted = val[1:end_idx]
            remainder = val[end_idx + 1:].strip()
            comment = remainder.lstrip('#').strip() if remainder.startswith('#') else None
            return extracted, comment

    if "#" in val:
        parts = val.split("#", 1)
        return parts[0].strip(), parts[1].strip()

    return val, None


def _find_matching_quote(s: str, quote_char: str) -> int:
    escaped = False
    for i in range(1, len(s)):
        ch = s[i]
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == quote_char:
            return i
    return -1


def parse_env_content(content: str, path: str = "<string>") -> EnvFile:
    lines = content.splitlines()
    entries: dict[str, EnvEntry] = {}

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        line_no = idx + 1

        if not stripped or stripped.startswith("#"):
            idx += 1
            continue

        match = _KEY_VAL_RE.match(line)
        if not match:
            if "=" in line:
                key_candidate = line.split("=", 1)[0].strip().replace("export ", "")
                raise ParseError(f"Invalid identifier '{key_candidate}' at line {line_no}", line_no, line)
            idx += 1
            continue

        key = match.group(1)
        raw_val = match.group(2)
        is_exported = bool(_EXPORT_PREFIX_RE.match(line))

        if (raw_val.startswith('"') and _find_matching_quote(raw_val, '"') == -1) or \
           (raw_val.startswith("'") and _find_matching_quote(raw_val, "'") == -1):
            quote_char = raw_val[0]
            accumulated = [raw_val[1:]]
            idx += 1
            closed = False
            while idx < len(lines):
                cur_line = lines[idx]
                if quote_char in cur_line:
                    end_idx = cur_line.find(quote_char)
                    accumulated.append(cur_line[:end_idx])
                    val = "\n".join(accumulated)
                    if quote_char == '"':
                        val = val.encode().decode("unicode_escape")
                    entries[key] = EnvEntry(
                        key=key,
                        value=val,
                        line_number=line_no,
                        raw_line=line,
                        comment=None,
                        is_exported=is_exported,
                    )
                    closed = True
                    break
                else:
                    accumulated.append(cur_line)
                    idx += 1

            if not closed:
                raise ParseError(f"Unclosed quote for key '{key}' starting at line {line_no}", line_no, line)
            idx += 1
            continue

        val, comment = _strip_quotes_and_comment(raw_val)
        entries[key] = EnvEntry(
            key=key,
            value=val,
            line_number=line_no,
            raw_line=line,
            comment=comment,
            is_exported=is_exported,
        )
        idx += 1

    return EnvFile(path=path, entries=entries, raw_lines=lines)


def parse_env_file(file_path: str | Path) -> EnvFile:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Environment file '{p}' not found")
    content = p.read_text(encoding="utf-8", errors="replace")
    return parse_env_content(content, path=str(p))

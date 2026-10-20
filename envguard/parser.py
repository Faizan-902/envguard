from __future__ import annotations

import re
from pathlib import Path
from .exceptions import ParseError
from .models import EnvEntry, EnvFile

_EXPORT_PREFIX_RE = re.compile(r"^\s*export\s+")
_KEY_VAL_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", re.DOTALL)

#: Escape sequences decoded inside double-quoted values. Only structural escapes
#: are decoded; every other backslash sequence is kept literally so Windows paths
#: such as ``"C:\Users\dev"``, ``"C:\temp"``, and ``"C:\new"`` survive parsing.
_DOUBLE_QUOTE_ESCAPES = {
    "\\": "\\",
    '"': '"',
    "'": "'",
}


def _decode_double_quoted(text: str) -> str:
    r"""Decode documented backslash escapes without re-encoding the text.

    ``bytes.decode("unicode_escape")`` is unsafe here: it mangles non-ASCII
    characters and raises ``UnicodeDecodeError`` on inputs like ``C:\Users``.
    """
    if "\\" not in text:
        return text

    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char != "\\" or index + 1 >= length:
            out.append(char)
            index += 1
            continue
        following = text[index + 1]
        replacement = _DOUBLE_QUOTE_ESCAPES.get(following)
        if replacement is None:
            out.append(char)
            out.append(following)
        else:
            out.append(replacement)
        index += 2
    return "".join(out)


def _find_unescaped(text: str, quote_char: str, start: int = 0) -> int:
    """Return the index of the first closing ``quote_char`` at or after ``start``.

    Inside double quotes a backslash escapes only ``\\`` and ``\"`` — the same
    pairs :func:`_decode_double_quoted` decodes — so ``"C:\\Users\\dev\\bin"``
    closes correctly. Single-quoted values are literal, so nothing escapes there.
    """
    index = start
    while index < len(text):
        char = text[index]
        if char == quote_char:
            return index
        if (
            char == "\\"
            and quote_char == '"'
            and index + 1 < len(text)
            and text[index + 1] in ('\\', '"')
        ):
            index += 2
            continue
        index += 1
    return -1


def _split_inline_comment(value: str) -> tuple[str, str | None]:
    """Split an unquoted value from a trailing ``#`` comment.

    A ``#`` only starts a comment at the start of the value or after whitespace,
    matching ``python-dotenv``, so ``PASSWORD=abc#123`` keeps its full value.
    """
    for index, char in enumerate(value):
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip(), value[index + 1 :].strip()
    return value, None


def _strip_quotes_and_comment(raw_val: str) -> tuple[str, str | None]:
    val = raw_val.strip()
    if not val:
        return "", None

    if val[0] in ("'", '"'):
        quote_char = val[0]
        end_idx = _find_unescaped(val, quote_char, 1)
        if end_idx != -1:
            inner = val[1:end_idx]
            extracted = _decode_double_quoted(inner) if quote_char == '"' else inner
            remainder = val[end_idx + 1 :].strip()
            comment = remainder[1:].strip() if remainder.startswith("#") else None
            return extracted, comment

    return _split_inline_comment(val)


def parse_env_content(content: str, path: str = "<string>") -> EnvFile:
    content = content.lstrip("\ufeff")
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

        if raw_val[:1] in ("'", '"') and _find_unescaped(raw_val, raw_val[0], 1) == -1:
            quote_char = raw_val[0]
            accumulated = raw_val[1:]
            comment: str | None = None
            idx += 1
            closed = False
            scan_from = 0
            while idx < len(lines):
                accumulated = f"{accumulated}\n{lines[idx]}"
                end_idx = _find_unescaped(accumulated, quote_char, scan_from)
                if end_idx != -1:
                    inner = accumulated[:end_idx]
                    val = _decode_double_quoted(inner) if quote_char == '"' else inner
                    remainder = accumulated[end_idx + 1 :].strip()
                    if remainder.startswith("#"):
                        comment = remainder[1:].strip()
                    elif remainder:
                        # A silently discarded remainder would merge two keys into
                        # one when a quoted value is followed by another assignment.
                        raise ParseError(
                            f"Unexpected content after the closing quote for key '{key}' at line {line_no}",
                            line_no,
                            line,
                        )
                    entries[key] = EnvEntry(
                        key=key,
                        value=val,
                        line_number=line_no,
                        raw_line=line,
                        comment=comment,
                        is_exported=is_exported,
                    )
                    closed = True
                    break
                # Resume scanning at the end of what we already checked; step back
                # one character when a trailing backslash may escape the next line.
                scan_from = len(accumulated) - 1 if accumulated.endswith("\\") else len(accumulated)
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
    try:
        content = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as err:
        raise ParseError(f"'{p}' is not valid UTF-8 ({err.reason} at byte {err.start})") from err
    return parse_env_content(content, path=str(p))

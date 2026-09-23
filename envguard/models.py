from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal


@dataclass
class EnvEntry:
    key: str
    value: str
    line_number: int
    raw_line: str
    comment: str | None = None
    is_exported: bool = False


@dataclass
class EnvFile:
    path: str
    entries: dict[str, EnvEntry] = field(default_factory=dict)
    raw_lines: list[str] = field(default_factory=list)

    def get(self, key: str, default: str | None = None) -> str | None:
        entry = self.entries.get(key)
        return entry.value if entry else default

    def __contains__(self, key: str) -> bool:
        return key in self.entries

    def __iter__(self) -> Iterator[EnvEntry]:
        return iter(self.entries.values())


@dataclass
class ValidationIssue:
    key: str
    issue_type: Literal["missing", "empty", "placeholder", "type_mismatch", "regex_mismatch", "syntax"]
    message: str
    line_number: int | None = None


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    checked_count: int = 0


@dataclass
class DiffResult:
    missing_in_target: list[str] = field(default_factory=list)
    extra_in_target: list[str] = field(default_factory=list)
    empty_in_target: list[str] = field(default_factory=list)
    matching_keys: list[str] = field(default_factory=list)

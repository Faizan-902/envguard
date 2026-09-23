from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Sequence
from urllib.parse import urlparse

from .models import EnvFile, ValidationIssue, ValidationResult

_PLACEHOLDER_PATTERNS = [
    re.compile(r"^<.*>$"),
    re.compile(r"^\[.*\]$"),
    re.compile(r"^\$\{.*\}$"),
    re.compile(r"^(?:your[_-]|my[_-]|insert[_-]|change[_-]|todo[_-])", re.IGNORECASE),
    re.compile(r"(?:changeme|todo|placeholder|dummy|example_key|secret_key|replace_me|your_key)", re.IGNORECASE),
    re.compile(r"^x{3,}$", re.IGNORECASE),
]

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_BOOL_TRUE = {"1", "true", "yes", "on", "t"}
_BOOL_FALSE = {"0", "false", "no", "off", "f"}


def _rule_allows_placeholder(rule: Rule, global_disallow: bool) -> bool:
    if rule.allow_placeholder is not None:
        return rule.allow_placeholder
    return not global_disallow


@dataclass
class Rule:
    key: str
    type: str = "string"
    required: bool = True
    allow_empty: bool = False
    allow_placeholder: bool | None = None
    choices: Sequence[str] | None = None
    regex: str | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    custom_validator: Callable[[str], bool | str] | None = None


def is_placeholder(value: str) -> bool:
    val = value.strip()
    if not val:
        return False
    return any(p.search(val) for p in _PLACEHOLDER_PATTERNS)


class EnvValidator:
    def __init__(self, rules: Sequence[Rule] | None = None, disallow_placeholders: bool = True):
        self.rules: dict[str, Rule] = {r.key: r for r in (rules or [])}
        self.disallow_placeholders = disallow_placeholders

    def add_rule(self, rule: Rule) -> EnvValidator:
        self.rules[rule.key] = rule
        return self

    def validate(self, env: EnvFile) -> ValidationResult:
        issues: list[ValidationIssue] = []
        checked_count = 0

        # Validate defined rules
        for key, rule in self.rules.items():
            checked_count += 1
            entry = env.entries.get(key)

            if entry is None:
                if rule.required:
                    issues.append(ValidationIssue(
                        key=key,
                        issue_type="missing",
                        message=f"Required variable '{key}' is missing",
                    ))
                continue

            val = entry.value

            if not val and not rule.allow_empty:
                issues.append(ValidationIssue(
                    key=key,
                    issue_type="empty",
                    message=f"Variable '{key}' cannot be empty",
                    line_number=entry.line_number,
                ))
                continue

            if val and not _rule_allows_placeholder(rule, self.disallow_placeholders):
                if is_placeholder(val):
                    issues.append(ValidationIssue(
                        key=key,
                        issue_type="placeholder",
                        message=f"Variable '{key}' contains unresolved placeholder: '{val}'",
                        line_number=entry.line_number,
                    ))

            # Type checking
            type_error = self._validate_type(val, rule)
            if type_error:
                issues.append(ValidationIssue(
                    key=key,
                    issue_type="type_mismatch",
                    message=f"Variable '{key}': {type_error}",
                    line_number=entry.line_number,
                ))

            # Regex check
            if rule.regex and val:
                if not re.search(rule.regex, val):
                    issues.append(ValidationIssue(
                        key=key,
                        issue_type="regex_mismatch",
                        message=f"Variable '{key}' value does not match regex pattern '{rule.regex}'",
                        line_number=entry.line_number,
                    ))

            # Custom validator check
            if rule.custom_validator and val:
                res = rule.custom_validator(val)
                if isinstance(res, str):
                    issues.append(ValidationIssue(
                        key=key,
                        issue_type="type_mismatch",
                        message=f"Variable '{key}': {res}",
                        line_number=entry.line_number,
                    ))
                elif res is False:
                    issues.append(ValidationIssue(
                        key=key,
                        issue_type="type_mismatch",
                        message=f"Variable '{key}' failed custom validation",
                        line_number=entry.line_number,
                    ))

        # Check for un-ruled placeholder entries in the env file
        for entry in env:
            if entry.key not in self.rules:
                checked_count += 1
                if self.disallow_placeholders and is_placeholder(entry.value):
                    issues.append(ValidationIssue(
                        key=entry.key,
                        issue_type="placeholder",
                        message=f"Variable '{entry.key}' contains unresolved placeholder: '{entry.value}'",
                        line_number=entry.line_number,
                    ))

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            checked_count=checked_count,
        )

    def _validate_type(self, val: str, rule: Rule) -> str | None:
        if not val and rule.allow_empty:
            return None

        t = rule.type.lower()
        if t == "string":
            return None

        elif t == "integer" or t == "int":
            try:
                num = int(val)
                if rule.min_value is not None and num < rule.min_value:
                    return f"Must be at least {rule.min_value}"
                if rule.max_value is not None and num > rule.max_value:
                    return f"Must be at most {rule.max_value}"
            except ValueError:
                return f"Expected integer, got '{val}'"

        elif t == "float" or t == "number":
            try:
                num = float(val)
                if rule.min_value is not None and num < rule.min_value:
                    return f"Must be at least {rule.min_value}"
                if rule.max_value is not None and num > rule.max_value:
                    return f"Must be at most {rule.max_value}"
            except ValueError:
                return f"Expected numeric float, got '{val}'"

        elif t == "boolean" or t == "bool":
            low = val.lower()
            if low not in _BOOL_TRUE and low not in _BOOL_FALSE:
                return f"Expected boolean (true/false, 1/0, yes/no), got '{val}'"

        elif t == "port":
            try:
                p = int(val)
                if not (1 <= p <= 65535):
                    return f"Port must be between 1 and 65535, got {p}"
            except ValueError:
                return f"Expected valid port number, got '{val}'"

        elif t == "url" or t == "uri":
            parsed = urlparse(val)
            if not parsed.scheme or not (parsed.netloc or parsed.path):
                return f"Expected valid URL, got '{val}'"

        elif t == "email":
            if not _EMAIL_RE.match(val):
                return f"Expected valid email address, got '{val}'"

        elif t == "json":
            try:
                json.loads(val)
            except json.JSONDecodeError as err:
                return f"Invalid JSON string: {err.msg}"

        elif t == "enum" or t == "choice":
            if rule.choices and val not in rule.choices:
                choices_str = ", ".join(repr(c) for c in rule.choices)
                return f"Value '{val}' not in allowed choices [{choices_str}]"

        return None

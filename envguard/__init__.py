"""envguard - Environment variable audit and validation toolkit."""

__version__ = "0.1.0"

from .models import EnvEntry, EnvFile, DiffResult, ValidationIssue, ValidationResult
from .parser import parse_env_file, parse_env_content
from .validator import EnvValidator, Rule, is_placeholder
from .syncer import compare_env_files, sync_env_files, generate_example_template

__all__ = [
    "EnvEntry",
    "EnvFile",
    "DiffResult",
    "ValidationIssue",
    "ValidationResult",
    "parse_env_file",
    "parse_env_content",
    "EnvValidator",
    "Rule",
    "is_placeholder",
    "compare_env_files",
    "sync_env_files",
    "generate_example_template",
]

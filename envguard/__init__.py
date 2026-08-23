"""envguard - Environment variable audit and validation toolkit."""

__version__ = "0.1.0"

from .models import EnvEntry, EnvFile, DiffResult, ValidationResult
from .parser import parse_env_file, parse_env_content

__all__ = [
    "EnvEntry",
    "EnvFile",
    "DiffResult",
    "ValidationResult",
    "parse_env_file",
    "parse_env_content",
]

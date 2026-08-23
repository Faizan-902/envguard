class EnvGuardError(Exception):
    """Base exception for all envguard errors."""
    pass


class ParseError(EnvGuardError):
    """Raised when parsing an environment file fails."""

    def __init__(self, message: str, line_number: int | None = None, line_content: str | None = None):
        super().__init__(message)
        self.line_number = line_number
        self.line_content = line_content


class ValidationError(EnvGuardError):
    """Raised when validation fails."""
    pass

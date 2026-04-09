"""Stable process exit codes and deterministic exception mapping."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes used by the CLI entrypoint.

    Attributes:
        OK: Successful completion.
        UNEXPECTED_ERROR: Unknown unhandled failure.
        INVALID_INPUT: User/config/input validation failure.
        IO_ERROR: Filesystem or IO-related failure.
        INTERRUPTED: User interrupt signal path.
    """

    OK = 0
    UNEXPECTED_ERROR = 1
    INVALID_INPUT = 2
    IO_ERROR = 3
    INTERRUPTED = 130

    def __repr__(self) -> str:
        """Return a stable debug representation."""
        return f"ExitCode.{self.name}"


_KNOWN_EXCEPTION_EXIT_CODES: tuple[tuple[type[BaseException], ExitCode], ...] = (
    (KeyboardInterrupt, ExitCode.INTERRUPTED),
    (FileNotFoundError, ExitCode.IO_ERROR),
    (PermissionError, ExitCode.IO_ERROR),
    (OSError, ExitCode.IO_ERROR),
    (TypeError, ExitCode.INVALID_INPUT),
    (ValueError, ExitCode.INVALID_INPUT),
)


def map_exception_to_exit_code(exc: BaseException) -> ExitCode:
    """Map one raised exception to its deterministic process exit code.

    Args:
        exc: Raised exception instance.

    Returns:
        One non-zero code for failures; unknown classes map to one fallback.
    """
    for exception_type, exit_code in _KNOWN_EXCEPTION_EXIT_CODES:
        if isinstance(exc, exception_type):
            return exit_code
    return ExitCode.UNEXPECTED_ERROR

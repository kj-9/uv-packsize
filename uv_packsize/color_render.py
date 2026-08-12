"""Opt-in ANSI decoration for terminal-safe human-readable reports."""

from __future__ import annotations

from enum import Enum


class ColorMode(Enum):
    """Public CLI color selection."""

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


_RESET = "\x1b[0m"
_BOLD_CYAN = "\x1b[1;36m"
_GREEN = "\x1b[32m"
_RED = "\x1b[31m"
_YELLOW = "\x1b[33m"


def should_color_report(
    mode: ColorMode,
    *,
    stdout_is_tty: bool,
    term: str | None,
    no_color_is_set: bool,
) -> bool:
    """Resolve color without consulting ambient process state."""

    if type(mode) is not ColorMode:
        raise TypeError("mode must be ColorMode")
    if type(stdout_is_tty) is not bool:
        raise TypeError("stdout_is_tty must be bool")
    if term is not None and type(term) is not str:
        raise TypeError("term must be str or None")
    if type(no_color_is_set) is not bool:
        raise TypeError("no_color_is_set must be bool")
    if mode is ColorMode.ALWAYS:
        return True
    if mode is ColorMode.NEVER:
        return False
    return stdout_is_tty and term != "dumb" and not no_color_is_set


def decorate_report(report: str) -> str:
    """Decorate fixed report structure while preserving all semantic text."""

    if type(report) is not str:
        raise TypeError("report must be str")
    return "".join(_decorate_line(line) for line in report.splitlines(keepends=True))


def _decorate_line(line: str) -> str:
    body, ending = _split_line_ending(line)
    if body.startswith("--- ") and body.endswith(" ---"):
        body = f"{_BOLD_CYAN}{body}{_RESET}"
    elif body.startswith("Warning: "):
        body = f"{_YELLOW}{body}{_RESET}"
    elif body == "Result: PASS":
        body = f"Result: {_GREEN}PASS{_RESET}"
    elif body == "Result: FAIL":
        body = f"Result: {_RED}FAIL{_RESET}"
    elif body == "Completeness: complete":
        body = f"Completeness: {_GREEN}complete{_RESET}"
    elif body == "Completeness: incomplete":
        body = f"Completeness: {_YELLOW}incomplete{_RESET}"
    return f"{body}{ending}"


def _split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""

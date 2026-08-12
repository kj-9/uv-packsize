"""Bounded ``pyproject.toml`` budget-policy source resolution.

This adapter has one deliberately narrow source: an explicit ``Path`` to a
``pyproject.toml`` file.  It performs no current-directory discovery, upward
search, environment lookup, or source merging.  An absent budget section means
that this source supplies no policy; an explicitly empty budget table is the
distinct, explicit no-op policy handled by :func:`parse_budget_policy`.

The reader follows symlinks in the ordinary ``Path`` manner.  It rejects a
regular file whose observable identity or rewrite metadata changes before,
during, or immediately after the bounded read.  This detects observable
rewrites; it does not claim filesystem-level immutable snapshot semantics.
"""

from __future__ import annotations

import io
import os
import stat
import sys
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import BinaryIO, Final, NoReturn, Protocol, cast

from .budget import BudgetPolicy
from .budget_config import parse_budget_policy

MAX_BUDGET_CONFIG_BYTES: Final = 1024 * 1024
_NATIVE_PATH_TYPE: Final = type(Path("."))
_FileSnapshot = tuple[int, int, int, int, int, int]


class _TomlLoader(Protocol):
    def load(self, source: BinaryIO, /) -> object: ...


try:
    _toml: _TomlLoader | None = cast(
        _TomlLoader,
        import_module("tomllib" if sys.version_info >= (3, 11) else "tomli"),
    )
except ImportError:  # pragma: no cover - packaging failure fallback.
    _toml = None


class BudgetPolicySourceErrorReason(str, Enum):
    """Stable, data-free reasons a policy source cannot be resolved."""

    FILE_NOT_FOUND = "file-not-found"
    NOT_REGULAR_FILE = "not-regular-file"
    CHANGED_FILE = "changed-file"
    READ_FAILED = "read-failed"
    SIZE_LIMIT = "size-limit"
    INVALID_ENCODING = "invalid-encoding"
    INVALID_TOML = "invalid-toml"
    INVALID_DOCUMENT = "invalid-document"
    INVALID_TOOL_SECTION = "invalid-tool-section"
    INVALID_UV_PACKSIZE_SECTION = "invalid-uv-packsize-section"
    INVALID_BUDGET_SECTION = "invalid-budget-section"
    PARSER_UNAVAILABLE = "parser-unavailable"


class BudgetPolicySourceSection(str, Enum):
    """Safe locations reported by source-resolution errors."""

    FILE = "file"
    DOCUMENT = "document"
    TOOL = "tool"
    UV_PACKSIZE = "tool.uv-packsize"
    BUDGET = "tool.uv-packsize.budget"


class BudgetPolicySourceError(ValueError):
    """A sanitized source error that never reflects a path or TOML contents."""

    def __init__(
        self,
        reason: BudgetPolicySourceErrorReason,
        section: BudgetPolicySourceSection,
    ) -> None:
        if type(reason) is not BudgetPolicySourceErrorReason:
            raise TypeError("reason must be a BudgetPolicySourceErrorReason")
        if type(section) is not BudgetPolicySourceSection:
            raise TypeError("section must be a BudgetPolicySourceSection")
        self.reason = reason
        self.section = section
        self.path = section.value
        super().__init__(
            f"Invalid budget policy source ({reason.value} at {section.value})."
        )


def _fail(
    reason: BudgetPolicySourceErrorReason, section: BudgetPolicySourceSection
) -> NoReturn:
    raise BudgetPolicySourceError(reason, section)


def load_budget_policy(path: Path) -> BudgetPolicy | None:
    """Read an explicit project file and return its policy, if configured.

    Missing ``[tool.uv-packsize.budget]`` returns ``None``.  A missing explicit
    file, malformed TOML, invalid section shape, and unsafe read boundary each
    raise :class:`BudgetPolicySourceError`.  Policy field validation is owned
    by :func:`parse_budget_policy` and its sanitized typed errors propagate.
    """

    if type(path) is not _NATIVE_PATH_TYPE:
        raise TypeError("path must be an exact native Path")
    payload = _read(path)
    document = _parse(payload)
    mapping = _budget_mapping(document)
    if mapping is None:
        return None
    return parse_budget_policy(mapping)


def _read(path: Path) -> bytes:  # noqa: PLR0912, PLR0915
    try:
        before = path.stat()
    except FileNotFoundError:
        _fail(
            BudgetPolicySourceErrorReason.FILE_NOT_FOUND, BudgetPolicySourceSection.FILE
        )
    except (OSError, ValueError):
        _fail(BudgetPolicySourceErrorReason.READ_FAILED, BudgetPolicySourceSection.FILE)
    if not stat.S_ISREG(before.st_mode):
        _fail(
            BudgetPolicySourceErrorReason.NOT_REGULAR_FILE,
            BudgetPolicySourceSection.FILE,
        )
    before_snapshot = _file_snapshot(before)
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        _fail(
            BudgetPolicySourceErrorReason.FILE_NOT_FOUND, BudgetPolicySourceSection.FILE
        )
    except (OSError, ValueError):
        _fail(BudgetPolicySourceErrorReason.READ_FAILED, BudgetPolicySourceSection.FILE)
    failure: BudgetPolicySourceError | None = None
    payload = b""
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            _fail(
                BudgetPolicySourceErrorReason.NOT_REGULAR_FILE,
                BudgetPolicySourceSection.FILE,
            )
        if _file_snapshot(opened) != before_snapshot:
            _fail(
                BudgetPolicySourceErrorReason.CHANGED_FILE,
                BudgetPolicySourceSection.FILE,
            )
        chunks: list[bytes] = []
        remaining = MAX_BUDGET_CONFIG_BYTES + 1
        while remaining:
            try:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > MAX_BUDGET_CONFIG_BYTES:
            _fail(
                BudgetPolicySourceErrorReason.SIZE_LIMIT,
                BudgetPolicySourceSection.FILE,
            )
        try:
            after_opened = os.fstat(descriptor)
        except FileNotFoundError:
            _fail(
                BudgetPolicySourceErrorReason.CHANGED_FILE,
                BudgetPolicySourceSection.FILE,
            )
        if not stat.S_ISREG(after_opened.st_mode):
            _fail(
                BudgetPolicySourceErrorReason.CHANGED_FILE,
                BudgetPolicySourceSection.FILE,
            )
        try:
            after_path = path.stat()
        except FileNotFoundError:
            _fail(
                BudgetPolicySourceErrorReason.CHANGED_FILE,
                BudgetPolicySourceSection.FILE,
            )
        if not stat.S_ISREG(after_path.st_mode):
            _fail(
                BudgetPolicySourceErrorReason.CHANGED_FILE,
                BudgetPolicySourceSection.FILE,
            )
        if (
            _file_snapshot(after_opened) != before_snapshot
            or _file_snapshot(after_path) != before_snapshot
        ):
            _fail(
                BudgetPolicySourceErrorReason.CHANGED_FILE,
                BudgetPolicySourceSection.FILE,
            )
    except BudgetPolicySourceError as error:
        failure = error
    except (OSError, ValueError):
        failure = BudgetPolicySourceError(
            BudgetPolicySourceErrorReason.READ_FAILED,
            BudgetPolicySourceSection.FILE,
        )
    close_failed = not _safe_close(descriptor)
    if failure is not None:
        raise failure
    if close_failed:
        _fail(BudgetPolicySourceErrorReason.READ_FAILED, BudgetPolicySourceSection.FILE)
    return payload


def _file_snapshot(value: os.stat_result) -> _FileSnapshot:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _safe_close(descriptor: int) -> bool:
    try:
        os.close(descriptor)
    except (OSError, ValueError):
        return False
    return True


def _parse(payload: bytes) -> dict[str, object]:
    if _toml is None:
        _fail(
            BudgetPolicySourceErrorReason.PARSER_UNAVAILABLE,
            BudgetPolicySourceSection.DOCUMENT,
        )
    try:
        document = _toml.load(io.BytesIO(payload))
    except UnicodeDecodeError:
        _fail(
            BudgetPolicySourceErrorReason.INVALID_ENCODING,
            BudgetPolicySourceSection.DOCUMENT,
        )
    except (TypeError, ValueError, OverflowError):
        _fail(
            BudgetPolicySourceErrorReason.INVALID_TOML,
            BudgetPolicySourceSection.DOCUMENT,
        )
    if type(document) is not dict:
        _fail(
            BudgetPolicySourceErrorReason.INVALID_DOCUMENT,
            BudgetPolicySourceSection.DOCUMENT,
        )
    return cast(dict[str, object], document)


def _budget_mapping(document: dict[str, object]) -> dict[str, object] | None:
    tool = _optional_table(
        document,
        "tool",
        BudgetPolicySourceErrorReason.INVALID_TOOL_SECTION,
        BudgetPolicySourceSection.TOOL,
    )
    if tool is None:
        return None
    package = _optional_table(
        tool,
        "uv-packsize",
        BudgetPolicySourceErrorReason.INVALID_UV_PACKSIZE_SECTION,
        BudgetPolicySourceSection.UV_PACKSIZE,
    )
    if package is None:
        return None
    budget = _optional_table(
        package,
        "budget",
        BudgetPolicySourceErrorReason.INVALID_BUDGET_SECTION,
        BudgetPolicySourceSection.BUDGET,
    )
    if budget is None:
        return None
    # ``tomllib`` already yields dicts, but make a fresh exact builtin mapping
    # so the pure parser receives its intentionally trusted input boundary.
    return dict(budget)


def _optional_table(
    parent: dict[str, object],
    key: str,
    reason: BudgetPolicySourceErrorReason,
    section: BudgetPolicySourceSection,
) -> dict[str, object] | None:
    if key not in parent:
        return None
    value = parent[key]
    if type(value) is not dict:
        _fail(reason, section)
    return cast(dict[str, object], value)

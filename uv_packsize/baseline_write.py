"""Pure fresh-baseline rendering and conservative POSIX publication."""

import errno
import os
import secrets
import stat
from pathlib import Path
from typing import NoReturn

from uv_packsize.baseline import (
    MAX_BASELINE_BYTES,
    BaselineError,
    analysis_result_to_baseline,
    parse_baseline_json,
)
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import AnalysisResult, ProjectLockContext, ResolutionContext
from uv_packsize.project_lock_json_render import render_project_lock_analysis_json

_NATIVE_PATH_TYPE = type(Path("."))


class BaselineWriteError(BaselineError):
    """Sanitized render or write failure; values and OS messages stay private."""

    def __init__(self, code: str, field: str = "document") -> None:
        super().__init__(code, field)


def _fail(code: str, field: str = "document") -> NoReturn:
    raise BaselineWriteError(code, field)


def render_fresh_baseline(result: AnalysisResult) -> bytes:
    """Return exactly the existing v1 UTF-8 JSON document for a fresh result."""

    if (
        type(result) is not AnalysisResult
        or type(result.context) is not ResolutionContext
    ):
        _fail("not-fresh-analysis")
    try:
        payload = render_analysis_json(result, schema_version=1).encode("utf-8")
        if len(payload) > MAX_BASELINE_BYTES:
            _fail("size-limit")
        if parse_baseline_json(payload) != analysis_result_to_baseline(result):
            _fail("projection-mismatch")
    except BaselineWriteError:
        raise
    except (BaselineError, UnicodeError, ValueError, TypeError, OverflowError):
        _fail("render-failed")
    return payload


def render_project_lock_baseline(result: AnalysisResult) -> bytes:
    """Return the closed v3 JSON document for one project-lock result."""

    if (
        type(result) is not AnalysisResult
        or type(result.context) is not ProjectLockContext
    ):
        _fail("not-project-lock-analysis")
    try:
        payload = render_project_lock_analysis_json(result).encode("utf-8")
        if len(payload) > MAX_BASELINE_BYTES:
            _fail("size-limit")
        if parse_baseline_json(payload) != analysis_result_to_baseline(result):
            _fail("projection-mismatch")
    except BaselineWriteError:
        raise
    except (BaselineError, UnicodeError, ValueError, TypeError, OverflowError):
        _fail("render-failed")
    return payload


def _validate_payload(payload: bytes) -> None:
    if type(payload) is not bytes:
        raise TypeError("payload must be bytes")
    if len(payload) > MAX_BASELINE_BYTES:
        _fail("size-limit")
    try:
        baseline = parse_baseline_json(payload)
    except BaselineError as error:
        _fail(error.code)
    if (baseline.schema_version, baseline.input_kind) not in {
        (1, "fresh-install"),
        (3, "project-lock"),
    }:
        _fail("unsupported-baseline")


def _features() -> None:
    required = (
        "open",
        "lstat",
        "fstat",
        "link",
        "unlink",
        "replace",
        "close",
        "fsync",
        "fchmod",
    )
    if (
        os.name != "posix"
        or not hasattr(os, "supports_dir_fd")
        or not all(hasattr(os, name) for name in required)
    ):
        _fail("unsupported-platform", "file")
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        _fail("unsupported-platform", "file")
    # CPython 3.11 and 3.12 accept ``dir_fd`` for ``lstat`` on Linux even
    # though they omit it from ``supports_dir_fd``.  Use ``lstat`` directly
    # for the no-follow primitive rather than substituting ``stat`` based on
    # that incomplete feature advertisement.  The remaining operations must
    # be advertised before opening a user-controlled path.
    if not {os.open, os.link, os.unlink}.issubset(os.supports_dir_fd):
        _fail("unsupported-platform", "file")


def _lstat(path: str, *, dir_fd: int | None = None) -> os.stat_result:
    """Return no-follow metadata through the native POSIX primitive."""

    return os.lstat(path, dir_fd=dir_fd)


def _effective_uid() -> int:
    getter = getattr(os, "geteuid", None) or getattr(os, "getuid", None)
    if getter is None:
        _fail("unsupported-platform", "file")
    try:
        return getter()
    except (OSError, TypeError, NotImplementedError, AttributeError):
        _fail("unsupported-platform", "file")


def _parts(path: Path) -> tuple[bool, tuple[str, ...], str]:
    if type(path) is not _NATIVE_PATH_TYPE:
        raise TypeError("path must be a Path")
    parts = path.parts
    absolute = path.is_absolute()
    values = parts[1:] if absolute else parts
    if not values or any(part in {"", ".", ".."} for part in values):
        _fail("invalid-path", "file")
    return absolute, tuple(values[:-1]), values[-1]


def _safe_close(fd: int) -> bool:
    try:
        os.close(fd)
        return True
    except (OSError, TypeError, NotImplementedError, AttributeError):
        return False


def _safe_unlink(name: str, parent: int) -> bool:
    try:
        os.unlink(name, dir_fd=parent)
        return True
    except (OSError, TypeError, NotImplementedError, AttributeError):
        return False


def _trusted_parent(item: os.stat_result, uid: int) -> bool:
    if not item.st_mode & 0o022:
        return True
    return item.st_uid == uid and bool(item.st_mode & stat.S_ISVTX)


def _open_parent(path: Path, uid: int) -> tuple[int, str]:  # noqa: PLR0912
    absolute, parents, name = _parts(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd: int | None = None
    try:
        anchor = "/" if absolute else "."
        before = _lstat(anchor)
        fd = os.open(anchor, flags)
        opened = os.fstat(fd)
        if not stat.S_ISDIR(opened.st_mode) or (before.st_dev, before.st_ino) != (
            opened.st_dev,
            opened.st_ino,
        ):
            _fail("changed-parent", "file")
        if not _trusted_parent(opened, uid):
            _fail("unsafe-parent", "file")
        for component in parents:
            before = _lstat(component, dir_fd=fd)
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
                _fail("unsafe-parent", "file")
            child: int | None = None
            try:
                child = os.open(component, flags, dir_fd=fd)
                opened = os.fstat(child)
                valid = (
                    stat.S_ISDIR(opened.st_mode)
                    and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino)
                    and _trusted_parent(opened, uid)
                )
            except (OSError, TypeError, NotImplementedError, AttributeError):
                if child is not None:
                    _safe_close(child)
                _fail("parent-unavailable", "file")
            if not valid:
                _safe_close(child)
                _fail("changed-parent", "file")
            _safe_close(fd)
            fd = child
        return fd, name
    except BaselineWriteError:
        if fd is not None:
            _safe_close(fd)
        raise
    except (OSError, TypeError, NotImplementedError, AttributeError):
        if fd is not None:
            _safe_close(fd)
        _fail("parent-unavailable", "file")


def _target(parent: int, name: str, absent: bool, uid: int) -> os.stat_result | None:
    try:
        item = _lstat(name, dir_fd=parent)
    except FileNotFoundError:
        if absent:
            return None
        _fail("changed-target", "file")
    except (OSError, TypeError, NotImplementedError, AttributeError):
        _fail("target-unavailable", "file")
    if stat.S_ISLNK(item.st_mode):
        _fail("symlink", "file")
    if not stat.S_ISREG(item.st_mode):
        _fail("not-regular-file", "file")
    if item.st_nlink != 1:
        _fail("hardlink", "file")
    if item.st_uid != uid:
        _fail("untrusted-target", "file")
    return item


def _identity(left: os.stat_result | None, right: os.stat_result | None) -> bool:
    return (
        left is right
        if left is None or right is None
        else (left.st_dev, left.st_ino, left.st_mode, left.st_uid)
        == (right.st_dev, right.st_ino, right.st_mode, right.st_uid)
    )


def _temp(parent: int) -> tuple[int, str, os.stat_result]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for _ in range(32):
        name = f".uv-packsize-{secrets.token_hex(16)}.tmp"
        try:
            fd = os.open(name, flags, 0o600, dir_fd=parent)
            try:
                item = os.fstat(fd)
            except (OSError, TypeError, NotImplementedError, AttributeError):
                _safe_close(fd)
                _safe_unlink(name, parent)
                _fail("temp-create-failed", "file")
            if not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
                _safe_close(fd)
                _safe_unlink(name, parent)
                _fail("changed-temp", "file")
            return fd, name, item
        except FileExistsError:
            continue
        except (OSError, TypeError, NotImplementedError, AttributeError):
            _fail("temp-create-failed", "file")
    _fail("temp-create-failed", "file")


def _write(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        try:
            count = os.write(fd, view)
        except InterruptedError:
            continue
        except (OSError, TypeError, NotImplementedError, AttributeError):
            _fail("write-failed", "file")
        if count <= 0:
            _fail("write-failed", "file")
        view = view[count:]


def _verify_temp(parent: int, name: str, fd: int, expected: os.stat_result) -> None:
    try:
        listed, opened = _lstat(name, dir_fd=parent), os.fstat(fd)
    except (OSError, TypeError, NotImplementedError, AttributeError):
        _fail("changed-temp", "file")
    expected_id = (expected.st_dev, expected.st_ino)
    if (
        not stat.S_ISREG(listed.st_mode)
        or listed.st_nlink != 1
        or (listed.st_dev, listed.st_ino) != expected_id
        or (opened.st_dev, opened.st_ino) != expected_id
    ):
        _fail("changed-temp", "file")


def write_baseline(path: Path, payload: bytes, *, overwrite: bool = False) -> None:  # noqa: PLR0912, PLR0915
    """Publish validated fresh bytes; unsupported platforms fail before I/O."""

    _validate_payload(payload)
    if type(overwrite) is not bool:
        raise TypeError("overwrite must be a bool")
    _features()
    uid = _effective_uid()
    parent, name = _open_parent(path, uid)
    temp_fd: int | None = None
    temp_name: str | None = None
    primary: BaselineWriteError | None = None
    committed = False
    try:
        before = _target(parent, name, True, uid)
        if before is not None and not overwrite:
            _fail("exists", "file")
        temp_fd, temp_name, temp_stat = _temp(parent)
        _write(temp_fd, payload)
        try:
            os.fchmod(temp_fd, 0o600)
            os.fsync(temp_fd)
        except (OSError, TypeError, NotImplementedError, AttributeError):
            _fail("file-fsync-failed", "file")
        _verify_temp(parent, temp_name, temp_fd, temp_stat)
        if overwrite:
            if not _identity(before, _target(parent, name, True, uid)):
                _fail("changed-target", "file")
            try:
                os.replace(temp_name, name, src_dir_fd=parent, dst_dir_fd=parent)
            except (OSError, TypeError, NotImplementedError, AttributeError):
                _fail("replace-failed", "file")
        else:
            try:
                os.link(
                    temp_name,
                    name,
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileExistsError:
                _fail("exists", "file")
            except (TypeError, NotImplementedError, AttributeError):
                _fail("no-clobber-unsupported", "file")
            except OSError as error:
                _fail(
                    "no-clobber-unsupported"
                    if error.errno in {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
                    else "link-failed",
                    "file",
                )
            if not _safe_unlink(temp_name, parent):
                committed = True
                _fail("committed-cleanup-failed", "file")
            temp_name = None
        committed = True
        temp_name = None
        final = _target(parent, name, False, uid)
        if final is None or stat.S_IMODE(final.st_mode) != 0o600:
            _fail("publish-validation-failed", "file")
        try:
            os.fsync(parent)
        except (OSError, TypeError, NotImplementedError, AttributeError):
            _fail("directory-fsync-failed", "file")
    except BaselineWriteError as error:
        primary = error
    finally:
        cleanup_failed = False
        if temp_name is not None:
            cleanup_failed = not _safe_unlink(temp_name, parent)
        if temp_fd is not None:
            cleanup_failed = not _safe_close(temp_fd) or cleanup_failed
        parent_closed = _safe_close(parent)
        if primary is None and (cleanup_failed or not parent_closed):
            primary = BaselineWriteError(
                "committed-cleanup-failed" if committed else "cleanup-failed", "file"
            )
    if primary is not None:
        raise primary

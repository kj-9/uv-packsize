"""Temporary, isolated ``uv sync`` bridge for validated project lock inputs.

This module has no CLI surface.  It accepts only the reader's private
same-read snapshot, materializes it under standard project filenames in a new
temporary directory, and removes that directory in every outcome.  It never
reopens a user-supplied project or lock path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Final, TypeVar, cast

from .models import BuildPolicy, DependencyGroupSelection
from .project_lock_reader import _ValidatedProjectLockSnapshot

_Result = TypeVar("_Result")
UvSyncRunner = Callable[[list[str], dict[str, str]], subprocess.CompletedProcess[str]]
InventoryCollector = Callable[[Path], _Result]

# ``uv sync`` needs a command-search path.  Windows also requires a small set
# of process variables to start executables reliably.  Everything else is
# deliberately omitted below: in particular no ambient ``UV_*``, virtual
# environment, index, source, or build setting may alter this private sync.
_WINDOWS_PROCESS_ENVIRONMENT_KEYS: Final = (
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
)


class ProjectLockInstallErrorReason(str, Enum):
    """Safe operational categories for the private installer bridge."""

    UV_SYNC_FAILED = "uv-sync-failed"
    INVENTORY_FAILED = "inventory-failed"
    UNEXPECTED = "unexpected"
    CLEANUP_FAILED = "cleanup-failed"


class ProjectLockInstallError(RuntimeError):
    """A typed bridge failure with no path, command, or uv diagnostic payload."""

    def __init__(self, reason: ProjectLockInstallErrorReason) -> None:
        if type(reason) is not ProjectLockInstallErrorReason:
            raise TypeError("reason must be a ProjectLockInstallErrorReason")
        self.reason = reason
        super().__init__(f"Could not install project lock (reason={reason.value}).")


def _run_uv_sync(
    command: list[str], environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run uv while deliberately keeping its diagnostics out of bridge errors."""

    project_index = command.index("--project")
    try:
        staged_project_directory = Path(command[project_index + 1])
    except IndexError:
        raise ValueError("uv sync command is missing a --project directory") from None

    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        cwd=staged_project_directory,
    )


def _isolated_uv_environment(target: Path) -> dict[str, str]:
    """Return the complete, minimal environment for a staged ``uv sync``.

    Project/lock mode has an explicit selection and build-policy contract.
    Starting from an empty mapping prevents a caller's configuration, indexes,
    source/build controls, or active virtual environment from changing that
    contract. ``UV_NO_CONFIG`` also prevents configuration discovery outside
    the staged project; the project metadata remains explicit through
    ``--project``.
    """

    environment = {"PATH": os.environ.get("PATH", os.defpath)}
    if os.name == "nt":
        for key in _WINDOWS_PROCESS_ENVIRONMENT_KEYS:
            value = os.environ.get(key)
            if value is not None:
                environment[key] = value
    environment["UV_PROJECT_ENVIRONMENT"] = str(target)
    # Do not let a fully isolated child fall back to a user cache. Keeping its
    # cache beside the target makes it both private to this sync and covered by
    # the bridge's unconditional temporary-root cleanup.
    environment["UV_CACHE_DIR"] = str(target.parent / "uv-cache")
    environment["UV_NO_CONFIG"] = "1"
    return environment


def install_validated_project_lock(  # noqa: PLR0912, PLR0915
    snapshot: _ValidatedProjectLockSnapshot,
    *,
    build_policy: BuildPolicy,
    collect_inventory: InventoryCollector[_Result],
    python_version: str | None = None,
    run_uv_sync: UvSyncRunner = _run_uv_sync,
) -> _Result:
    """Sync a private snapshot into a temporary prefix and collect its inventory.

    The target is an absolute path beneath a unique temporary root.  Both the
    target and the staged standard-name project files are always removed before
    this function returns or raises.  No input path or temporary path is
    exposed through results or typed failures.
    """

    if type(snapshot) is not _ValidatedProjectLockSnapshot:
        raise TypeError("snapshot must be a validated private project lock snapshot")
    if not isinstance(build_policy, BuildPolicy):
        raise TypeError("build_policy must be a BuildPolicy")
    if not callable(collect_inventory):
        raise TypeError("collect_inventory must be callable")
    if not callable(run_uv_sync):
        raise TypeError("run_uv_sync must be callable")

    temporary_root: Path | None = None
    primary_error: ProjectLockInstallError | None = None
    cleanup_error: ProjectLockInstallError | None = None
    result: _Result | None = None
    completed = False
    try:
        temporary_root = Path(tempfile.mkdtemp(prefix="uv-packsize-project-lock-"))
        stage = temporary_root / "stage"
        stage.mkdir()
        staged_project = stage / "pyproject.toml"
        staged_lock = stage / "uv.lock"
        staged_project.write_bytes(snapshot._project_bytes)
        staged_lock.write_bytes(snapshot._lock_bytes)

        target = temporary_root / "environment"
        environment = _isolated_uv_environment(target)
        command = _sync_command(snapshot, stage, build_policy, python_version)
        try:
            sync_result = run_uv_sync(command, environment)
        except Exception:
            raise ProjectLockInstallError(
                ProjectLockInstallErrorReason.UNEXPECTED
            ) from None
        if not isinstance(sync_result, subprocess.CompletedProcess):
            raise ProjectLockInstallError(ProjectLockInstallErrorReason.UNEXPECTED)
        if sync_result.returncode != 0:
            raise ProjectLockInstallError(ProjectLockInstallErrorReason.UV_SYNC_FAILED)
        try:
            result = collect_inventory(target)
        except Exception:
            raise ProjectLockInstallError(
                ProjectLockInstallErrorReason.INVENTORY_FAILED
            ) from None
        completed = True
    except ProjectLockInstallError as error:
        primary_error = error
    except Exception:
        primary_error = ProjectLockInstallError(
            ProjectLockInstallErrorReason.UNEXPECTED
        )
    finally:
        if temporary_root is not None:
            try:
                shutil.rmtree(temporary_root)
            except Exception:
                cleanup_error = ProjectLockInstallError(
                    ProjectLockInstallErrorReason.CLEANUP_FAILED
                )

    if cleanup_error is not None:
        raise cleanup_error
    if primary_error is not None:
        raise primary_error
    if not completed:
        raise ProjectLockInstallError(ProjectLockInstallErrorReason.UNEXPECTED)
    return cast(_Result, result)


def _sync_command(
    snapshot: _ValidatedProjectLockSnapshot,
    stage: Path,
    build_policy: BuildPolicy,
    python_version: str | None = None,
) -> list[str]:
    """Build an explicit uv argv solely from validated selection and policy."""

    selection = snapshot.selection
    command = [
        "uv",
        "sync",
        "--project",
        str(stage),
        "--locked",
        "--no-install-project",
        "--no-default-groups",
    ]
    if python_version is not None:
        if not isinstance(python_version, str) or not python_version:
            raise TypeError("python_version must be a non-empty string or None")
        command.extend(("--python", python_version))
    if selection.dependency_group_selection is DependencyGroupSelection.ALL:
        command.append("--all-groups")
    elif selection.dependency_group_selection is DependencyGroupSelection.EXPLICIT:
        for group in selection.dependency_groups:
            command.extend(("--group", group))
    elif selection.dependency_group_selection is not DependencyGroupSelection.NONE:
        raise TypeError("snapshot has an invalid dependency group selection")
    for extra in selection.extras:
        command.extend(("--extra", extra))
    if build_policy is BuildPolicy.WHEEL_ONLY:
        command.append("--no-build")
    elif build_policy is not BuildPolicy.ALLOW_BUILD:
        raise TypeError("build_policy must be a BuildPolicy")
    return command

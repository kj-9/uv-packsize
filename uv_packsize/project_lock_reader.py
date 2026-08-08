"""Read a deliberately small, stable subset of explicit project lock inputs.

This is not a general ``uv.lock`` parser.  It accepts only the tested
``version = 1`` / ``revision = 3`` subset needed to validate a root project,
its selected dependency groups and extras.  Standard build configuration and
resolved artifact records are validated then ignored; selection-affecting
fields remain closed and checked.  It never runs ``uv``, discovers a project,
or retains source locations, TOML values, URLs, credentials, or lock package
identifiers in its result or failures.
"""

from __future__ import annotations

import io
import os
import stat
import sys
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import BinaryIO, Final, NoReturn, Protocol, cast

from .models import DependencyGroupSelection, normalize_distribution_name

MAX_PROJECT_LOCK_INPUT_BYTES: Final = 8 * 1024 * 1024
_LOCK_IDENTITY_DOMAIN: Final = b"uv-packsize/project-lock/v1\0lock\0"
_NATIVE_PATH_TYPE: Final = type(Path("."))
_PROJECT_TOP_LEVEL_KEYS: Final = frozenset(
    {"project", "dependency-groups", "build-system", "tool"}
)
_PROJECT_KEYS: Final = frozenset(
    {
        "name",
        "version",
        "description",
        "readme",
        "requires-python",
        "license",
        "license-files",
        "authors",
        "maintainers",
        "classifiers",
        "keywords",
        "urls",
        "scripts",
        "gui-scripts",
        "entry-points",
        "dependencies",
        "optional-dependencies",
        "dynamic",
    }
)
_BUILD_SYSTEM_KEYS: Final = frozenset({"requires", "build-backend", "backend-path"})
# ``default-groups`` changes the implicit group selection made by uv commands.
# The explicit reader always reports the caller's selection, so it cannot safely
# represent a project-configured implicit selection. Other ``tool.uv`` settings
# are deliberately not rejected merely because they are present: they do not
# select dependency groups, and this is not a general uv configuration parser.
_TOOL_UV_GROUP_SELECTION_KEYS: Final = frozenset({"default-groups"})
_LOCK_TOP_LEVEL_KEYS: Final = frozenset(
    {"version", "revision", "requires-python", "options", "package"}
)
_LOCK_OPTIONS_KEYS: Final = frozenset({"prerelease-mode"})
_ROOT_PACKAGE_KEYS: Final = frozenset(
    {
        "name",
        "version",
        "source",
        "dependencies",
        "dev-dependencies",
        "optional-dependencies",
        "metadata",
        "sdist",
        "wheels",
    }
)
_NONROOT_PACKAGE_KEYS: Final = frozenset(
    {"name", "version", "source", "dependencies", "sdist", "wheels"}
)
_LOCK_DEPENDENCY_KEYS: Final = frozenset({"name", "marker", "extra"})
_PACKAGE_METADATA_KEYS: Final = frozenset(
    {"requires-dist", "requires-dev", "requires-python", "provides-extras"}
)
_LOCK_ARTIFACT_KEYS: Final = frozenset({"url", "hash", "size", "upload-time"})


class _TomlLoader(Protocol):
    def load(self, source: BinaryIO, /) -> object: ...


try:
    _toml: _TomlLoader | None = cast(
        _TomlLoader,
        import_module("tomllib" if sys.version_info >= (3, 11) else "tomli"),
    )
except ImportError:  # pragma: no cover - packaging failure fallback.
    _toml = None


class ProjectLockInputErrorReason(str, Enum):
    """Stable, data-free causes for refusing explicit project/lock inputs."""

    FILE_NOT_FOUND = "file-not-found"
    NOT_REGULAR_FILE = "not-regular-file"
    CHANGED_FILE = "changed-file"
    READ_FAILED = "read-failed"
    SIZE_LIMIT = "size-limit"
    INVALID_ENCODING = "invalid-encoding"
    INVALID_TOML = "invalid-toml"
    PARSER_UNAVAILABLE = "parser-unavailable"
    INVALID_PROJECT = "invalid-project"
    UNSUPPORTED_PROJECT_LOCK = "unsupported-project-lock"
    INVALID_SELECTION = "invalid-selection"
    AMBIGUOUS_SELECTION = "ambiguous-selection"


class ProjectLockInputField(str, Enum):
    """Safe input locations for reader diagnostics."""

    PROJECT_FILE = "project-file"
    LOCK_FILE = "lock-file"
    PROJECT = "project"
    LOCK = "lock"
    ROOT_PACKAGE = "root-package"
    WORKSPACE_MEMBER = "workspace-member"
    DEPENDENCY_GROUP = "dependency-group"
    EXTRA = "extra"


class ProjectLockInputError(ValueError):
    """A typed diagnostic that deliberately has no raw input payload."""

    def __init__(
        self, reason: ProjectLockInputErrorReason, field: ProjectLockInputField
    ) -> None:
        if type(reason) is not ProjectLockInputErrorReason:
            raise TypeError("reason must be a ProjectLockInputErrorReason")
        if type(field) is not ProjectLockInputField:
            raise TypeError("field must be a ProjectLockInputField")
        self.reason = reason
        self.field = field
        super().__init__(
            f"Invalid project lock input ({reason.value} at {field.value})."
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectLockSelection:
    """Validated explicit selection, without project paths or lock contents."""

    root_package: str
    workspace_member: str | None
    dependency_group_selection: DependencyGroupSelection
    dependency_groups: tuple[str, ...]
    extras: tuple[str, ...]
    lock_identity: str


def read_project_lock(  # noqa: PLR0913
    project: Path,
    lockfile: Path,
    *,
    workspace_member: str | None = None,
    dependency_groups: tuple[str, ...] = (),
    all_groups: bool = False,
    extras: tuple[str, ...] = (),
) -> ProjectLockSelection:
    """Safely read and validate explicit project and lockfile snapshots.

    The result is a narrow input projection for a later installer bridge.  No
    CLI, resolver, workspace-metadata command, network operation, or ambient
    project discovery is part of this boundary.
    """

    _require_exact_paths(project, lockfile)
    request = _selection_request(
        workspace_member, dependency_groups, all_groups, extras
    )
    project_document = _parse(
        _read_regular_snapshot(project, ProjectLockInputField.PROJECT_FILE),
        ProjectLockInputField.PROJECT,
    )
    lock_bytes = _read_regular_snapshot(lockfile, ProjectLockInputField.LOCK_FILE)
    lock_document = _parse(lock_bytes, ProjectLockInputField.LOCK)
    root_name, project_groups, project_extras = _project_semantics(project_document)
    packages = _lock_semantics(lock_document)
    root_package = packages.get(root_name)
    if root_package is None:
        _fail(
            ProjectLockInputErrorReason.INVALID_SELECTION,
            ProjectLockInputField.ROOT_PACKAGE,
        )
    _validate_root_source(root_package)
    _validate_nonroot_sources(packages, root_name)
    selected_member, selection, selected_groups, selected_extras = request
    if selected_member is not None:
        if selected_member != root_name:
            _fail(
                ProjectLockInputErrorReason.INVALID_SELECTION,
                ProjectLockInputField.WORKSPACE_MEMBER,
            )
        selected_member = root_name
    available_groups = _root_named_dependencies(root_package, "dev-dependencies")
    if set(project_groups) != set(available_groups):
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.DEPENDENCY_GROUP,
        )
    available_extras = _root_named_dependencies(root_package, "optional-dependencies")
    if set(project_extras) != set(available_extras):
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.EXTRA,
        )
    if selection is DependencyGroupSelection.ALL:
        selected_groups = tuple(sorted(available_groups))
    elif any(group not in available_groups for group in selected_groups):
        _fail(
            ProjectLockInputErrorReason.INVALID_SELECTION,
            ProjectLockInputField.DEPENDENCY_GROUP,
        )
    if any(extra not in available_extras for extra in selected_extras):
        _fail(
            ProjectLockInputErrorReason.INVALID_SELECTION, ProjectLockInputField.EXTRA
        )
    return ProjectLockSelection(
        root_package=root_name,
        workspace_member=selected_member,
        dependency_group_selection=selection,
        dependency_groups=selected_groups,
        extras=selected_extras,
        lock_identity=sha256(_LOCK_IDENTITY_DOMAIN + lock_bytes).hexdigest(),
    )


def _require_exact_paths(project: Path, lockfile: Path) -> None:
    if (
        type(project) is not _NATIVE_PATH_TYPE
        or type(lockfile) is not _NATIVE_PATH_TYPE
    ):
        raise TypeError("project and lockfile must be exact native Path values")


def _selection_request(
    workspace_member: str | None,
    dependency_groups: tuple[str, ...],
    all_groups: bool,
    extras: tuple[str, ...],
) -> tuple[str | None, DependencyGroupSelection, tuple[str, ...], tuple[str, ...]]:
    if type(all_groups) is not bool:
        raise TypeError("all_groups must be a bool")
    if workspace_member is not None:
        if type(workspace_member) is not str:
            _fail(
                ProjectLockInputErrorReason.INVALID_SELECTION,
                ProjectLockInputField.WORKSPACE_MEMBER,
            )
        member = _normalized_label(
            workspace_member, ProjectLockInputField.WORKSPACE_MEMBER
        )
    else:
        member = None
    groups = _normalized_labels(
        dependency_groups, ProjectLockInputField.DEPENDENCY_GROUP
    )
    selected_extras = _normalized_labels(extras, ProjectLockInputField.EXTRA)
    if all_groups and groups:
        _fail(
            ProjectLockInputErrorReason.INVALID_SELECTION,
            ProjectLockInputField.DEPENDENCY_GROUP,
        )
    mode = (
        DependencyGroupSelection.ALL
        if all_groups
        else DependencyGroupSelection.EXPLICIT
        if groups
        else DependencyGroupSelection.NONE
    )
    return member, mode, groups, selected_extras


def _normalized_labels(
    values: tuple[str, ...], field: ProjectLockInputField
) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{field.value} values must be a tuple of strings")
    normalized = tuple(_normalized_label(value, field) for value in values)
    if len(set(normalized)) != len(normalized):
        _fail(ProjectLockInputErrorReason.AMBIGUOUS_SELECTION, field)
    return tuple(sorted(normalized))


def _normalized_label(value: object, field: ProjectLockInputField) -> str:
    try:
        return normalize_distribution_name(cast(str, value))
    except (TypeError, ValueError):
        _fail(ProjectLockInputErrorReason.INVALID_SELECTION, field)


def _read_regular_snapshot(  # noqa: PLR0912, PLR0915
    path: Path, field: ProjectLockInputField
) -> bytes:
    _reject_symlink_components(path, field)
    try:
        before = path.lstat()
    except FileNotFoundError:
        _fail(ProjectLockInputErrorReason.FILE_NOT_FOUND, field)
    except (OSError, ValueError):
        _fail(ProjectLockInputErrorReason.READ_FAILED, field)
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        _fail(ProjectLockInputErrorReason.NOT_REGULAR_FILE, field)
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags | nofollow)
    except FileNotFoundError:
        _fail(ProjectLockInputErrorReason.FILE_NOT_FOUND, field)
    except (OSError, ValueError):
        _fail(ProjectLockInputErrorReason.READ_FAILED, field)
    payload = b""
    failure: ProjectLockInputError | None = None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _metadata_snapshot(
            opened
        ) != _metadata_snapshot(before):
            _fail(ProjectLockInputErrorReason.CHANGED_FILE, field)
        chunks: list[bytes] = []
        remaining = MAX_PROJECT_LOCK_INPUT_BYTES + 1
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
        after_opened = os.fstat(descriptor)
        after_path = path.lstat()
        if _metadata_snapshot(after_opened) != _metadata_snapshot(
            before
        ) or _metadata_snapshot(after_path) != _metadata_snapshot(before):
            _fail(ProjectLockInputErrorReason.CHANGED_FILE, field)
    except ProjectLockInputError as error:
        failure = error
    except (OSError, ValueError):
        failure = ProjectLockInputError(ProjectLockInputErrorReason.READ_FAILED, field)
    try:
        os.close(descriptor)
    except (OSError, ValueError):
        if failure is None:
            failure = ProjectLockInputError(
                ProjectLockInputErrorReason.READ_FAILED, field
            )
    if failure is not None:
        raise failure
    if len(payload) > MAX_PROJECT_LOCK_INPUT_BYTES:
        _fail(ProjectLockInputErrorReason.SIZE_LIMIT, field)
    return payload


def _reject_symlink_components(path: Path, field: ProjectLockInputField) -> None:
    """Reject a leaf or parent symlink without resolving a supplied path."""

    candidate = path if path.is_absolute() else Path.cwd() / path
    current = Path(candidate.anchor)
    for component in candidate.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            _fail(ProjectLockInputErrorReason.FILE_NOT_FOUND, field)
        except (OSError, ValueError):
            _fail(ProjectLockInputErrorReason.READ_FAILED, field)
        if stat.S_ISLNK(metadata.st_mode):
            _fail(ProjectLockInputErrorReason.NOT_REGULAR_FILE, field)


def _metadata_snapshot(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    """Return the metadata needed to detect an observable concurrent rewrite."""

    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _parse(payload: bytes, field: ProjectLockInputField) -> dict[str, object]:
    if _toml is None:
        _fail(ProjectLockInputErrorReason.PARSER_UNAVAILABLE, field)
    try:
        document = _toml.load(io.BytesIO(payload))
    except UnicodeDecodeError:
        _fail(ProjectLockInputErrorReason.INVALID_ENCODING, field)
    except (TypeError, ValueError, OverflowError):
        _fail(ProjectLockInputErrorReason.INVALID_TOML, field)
    if type(document) is not dict:
        _fail(ProjectLockInputErrorReason.INVALID_TOML, field)
    return cast(dict[str, object], document)


def _project_semantics(
    document: dict[str, object],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    _closed_table(
        document,
        _PROJECT_TOP_LEVEL_KEYS,
        ProjectLockInputErrorReason.INVALID_PROJECT,
        ProjectLockInputField.PROJECT,
    )
    project = _table(
        document.get("project"),
        ProjectLockInputErrorReason.INVALID_PROJECT,
        ProjectLockInputField.PROJECT,
    )
    _closed_table(
        project,
        _PROJECT_KEYS,
        ProjectLockInputErrorReason.INVALID_PROJECT,
        ProjectLockInputField.PROJECT,
    )
    _validate_ignored_project_tables(document)
    _validate_project_dynamic(project)
    root_name = _normalized_project_name(
        project.get("name"), ProjectLockInputField.ROOT_PACKAGE
    )
    groups = _named_project_requirement_keys(
        document.get("dependency-groups"),
        ProjectLockInputErrorReason.INVALID_PROJECT,
        ProjectLockInputField.DEPENDENCY_GROUP,
    )
    extras = _named_project_requirement_keys(
        project.get("optional-dependencies"),
        ProjectLockInputErrorReason.INVALID_PROJECT,
        ProjectLockInputField.EXTRA,
    )
    return root_name, groups, extras


def _lock_semantics(document: dict[str, object]) -> dict[str, dict[str, object]]:
    _closed_table(
        document,
        _LOCK_TOP_LEVEL_KEYS,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.LOCK,
    )
    if document.get("version") != 1 or document.get("revision") != 3:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )
    _validate_lock_context(document)
    package_values = document.get("package")
    if type(package_values) is not list or not package_values:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )
    packages: dict[str, dict[str, object]] = {}
    for value in package_values:
        package = _table(
            value,
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )
        name_value = package.get("name")
        name = _normalized_lock_name(name_value, ProjectLockInputField.LOCK)
        is_root_candidate = name not in packages and package.get("source") == {
            "editable": "."
        }
        _closed_table(
            package,
            _ROOT_PACKAGE_KEYS if is_root_candidate else _NONROOT_PACKAGE_KEYS,
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )
        version = package.get("version")
        source = package.get("source")
        if type(version) is not str or not version or type(source) is not dict:
            _fail(
                ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
                ProjectLockInputField.LOCK,
            )
        _validate_source(cast(dict[str, object], source))
        _validate_dependency_list(
            package.get("dependencies", []), ProjectLockInputField.LOCK
        )
        _validate_artifacts(package, ProjectLockInputField.LOCK)
        if is_root_candidate:
            _lock_named_dependencies(package, "dev-dependencies")
            _lock_named_dependencies(package, "optional-dependencies")
            _validate_package_metadata(package)
        if name in packages:
            _fail(
                ProjectLockInputErrorReason.AMBIGUOUS_SELECTION,
                ProjectLockInputField.ROOT_PACKAGE,
            )
        packages[name] = package
    return packages


def _validate_source(source: dict[str, object]) -> None:
    if len(source) != 1:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )
    kind, value = next(iter(source.items()))
    if kind not in {"registry", "editable"} or type(value) is not str or not value:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )


def _validate_ignored_project_tables(document: dict[str, object]) -> None:
    """Validate standard non-selection project tables before ignoring them."""

    build_system = document.get("build-system")
    if build_system is not None:
        _closed_table(
            _table(
                build_system,
                ProjectLockInputErrorReason.INVALID_PROJECT,
                ProjectLockInputField.PROJECT,
            ),
            _BUILD_SYSTEM_KEYS,
            ProjectLockInputErrorReason.INVALID_PROJECT,
            ProjectLockInputField.PROJECT,
        )
    tool = document.get("tool")
    if tool is not None:
        tool_table = _table(
            tool,
            ProjectLockInputErrorReason.INVALID_PROJECT,
            ProjectLockInputField.PROJECT,
        )
        _validate_tool_uv_group_selection(tool_table)


def _validate_tool_uv_group_selection(tool: dict[str, object]) -> None:
    """Reject uv configuration that changes implicit group selection.

    ``tool.uv.default-groups`` is rejected regardless of its value. Parsing a
    value here would make an unrequested selection appear as ``NONE`` or
    overload the explicit reader API. Unrelated ``tool.uv`` settings remain
    outside this boundary instead of turning it into a broad config allowlist.
    """

    uv = tool.get("uv")
    if uv is None:
        return
    uv_table = _table(
        uv,
        ProjectLockInputErrorReason.INVALID_PROJECT,
        ProjectLockInputField.PROJECT,
    )
    if _TOOL_UV_GROUP_SELECTION_KEYS.intersection(uv_table):
        _fail(
            ProjectLockInputErrorReason.INVALID_PROJECT,
            ProjectLockInputField.DEPENDENCY_GROUP,
        )


def _validate_project_dynamic(project: dict[str, object]) -> None:
    """Reject dynamic extras because their selectable names are not in the file."""

    dynamic = project.get("dynamic")
    if dynamic is None:
        return
    if type(dynamic) is not list or any(type(value) is not str for value in dynamic):
        _fail(
            ProjectLockInputErrorReason.INVALID_PROJECT, ProjectLockInputField.PROJECT
        )
    if "optional-dependencies" in dynamic:
        _fail(ProjectLockInputErrorReason.INVALID_PROJECT, ProjectLockInputField.EXTRA)


def _validate_lock_context(document: dict[str, object]) -> None:
    """Validate lock context fields that are retained only in the fingerprint."""

    requires_python = document.get("requires-python")
    if type(requires_python) is not str or not requires_python:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )
    options = _table(
        document.get("options"),
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.LOCK,
    )
    _closed_table(
        options,
        _LOCK_OPTIONS_KEYS,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.LOCK,
    )
    prerelease_mode = options.get("prerelease-mode")
    if prerelease_mode not in {
        "allow",
        "disallow",
        "explicit",
        "if-necessary",
        "if-necessary-or-explicit",
    }:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.LOCK,
        )


def _validate_artifacts(
    package: dict[str, object], field: ProjectLockInputField
) -> None:
    """Validate ignored v1 artifact records without retaining their locations."""

    sdist = package.get("sdist")
    if sdist is not None:
        _validate_artifact(sdist, field)
    wheels = package.get("wheels")
    if wheels is not None:
        if type(wheels) is not list or not wheels:
            _fail(ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field)
        for wheel in wheels:
            _validate_artifact(wheel, field)


def _validate_artifact(value: object, field: ProjectLockInputField) -> None:
    artifact = _table(
        value, ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field
    )
    _closed_table(
        artifact,
        _LOCK_ARTIFACT_KEYS,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        field,
    )
    if (
        type(artifact.get("url")) is not str
        or not artifact["url"]
        or type(artifact.get("hash")) is not str
        or not artifact["hash"]
        or type(artifact.get("size")) is not int
        or type(artifact.get("upload-time")) is not str
        or not artifact["upload-time"]
    ):
        _fail(ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field)


def _validate_package_metadata(package: dict[str, object]) -> None:
    metadata = package.get("metadata")
    if metadata is None:
        return
    table = _table(
        metadata,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.ROOT_PACKAGE,
    )
    _closed_table(
        table,
        _PACKAGE_METADATA_KEYS,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.ROOT_PACKAGE,
    )
    _validate_dependency_list(
        table.get("requires-dist", []), ProjectLockInputField.ROOT_PACKAGE
    )
    _lock_metadata_named_dependencies(table, "requires-dev")
    requires_python = table.get("requires-python")
    if requires_python is not None and (
        type(requires_python) is not str or not requires_python
    ):
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.ROOT_PACKAGE,
        )
    provided_extras = table.get("provides-extras")
    if provided_extras is not None:
        if type(provided_extras) is not list:
            _fail(
                ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
                ProjectLockInputField.ROOT_PACKAGE,
            )
        for extra in provided_extras:
            _normalized_lock_name(extra, ProjectLockInputField.ROOT_PACKAGE)


def _validate_root_source(package: dict[str, object]) -> None:
    source = cast(dict[str, object], package["source"])
    if source != {"editable": "."}:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.ROOT_PACKAGE,
        )


def _validate_nonroot_sources(
    packages: dict[str, dict[str, object]], root_name: str
) -> None:
    for name, package in packages.items():
        if name == root_name:
            continue
        source = cast(dict[str, object], package["source"])
        if set(source) != {"registry"}:
            _fail(
                ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
                ProjectLockInputField.LOCK,
            )


def _root_named_dependencies(package: dict[str, object], key: str) -> tuple[str, ...]:
    names = _lock_named_dependencies(package, key)
    metadata = package.get("metadata")
    if metadata is None:
        return names
    metadata_table = _table(
        metadata,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.ROOT_PACKAGE,
    )
    metadata_key = "requires-dev" if key == "dev-dependencies" else "provides-extras"
    metadata_names = _lock_metadata_named_dependencies(metadata_table, metadata_key)
    if metadata_key in metadata_table and metadata_names != names:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.ROOT_PACKAGE,
        )
    return names


def _lock_named_dependencies(package: dict[str, object], key: str) -> tuple[str, ...]:
    value = package.get(key, {})
    if type(value) is not dict:
        _fail(
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            ProjectLockInputField.ROOT_PACKAGE,
        )
    names = _named_table_keys(
        value,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.ROOT_PACKAGE,
    )
    for dependency_list in value.values():
        _validate_dependency_list(dependency_list, ProjectLockInputField.ROOT_PACKAGE)
    return names


def _lock_metadata_named_dependencies(
    metadata: dict[str, object], key: str
) -> tuple[str, ...]:
    if key == "provides-extras":
        values = metadata.get(key)
        if values is None:
            return ()
        if type(values) is not list:
            _fail(
                ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
                ProjectLockInputField.ROOT_PACKAGE,
            )
        names = tuple(
            _normalized_lock_name(value, ProjectLockInputField.ROOT_PACKAGE)
            for value in values
        )
        if len(set(names)) != len(names):
            _fail(
                ProjectLockInputErrorReason.AMBIGUOUS_SELECTION,
                ProjectLockInputField.ROOT_PACKAGE,
            )
        return tuple(sorted(names))
    value = metadata.get(key, {})
    names = _named_table_keys(
        value,
        ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
        ProjectLockInputField.ROOT_PACKAGE,
    )
    for dependency_list in cast(dict[str, object], value).values():
        _validate_dependency_list(dependency_list, ProjectLockInputField.ROOT_PACKAGE)
    return names


def _validate_dependency_list(value: object, field: ProjectLockInputField) -> None:
    if type(value) is not list:
        _fail(ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field)
    for dependency in value:
        table = _table(
            dependency, ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field
        )
        _closed_table(
            table,
            _LOCK_DEPENDENCY_KEYS,
            ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK,
            field,
        )
        _normalized_lock_name(table.get("name"), field)
        for key in ("marker", "extra"):
            value = table.get(key)
            if value is not None and (type(value) is not str or not value):
                _fail(ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field)


def _named_table_keys(
    value: object, reason: ProjectLockInputErrorReason, field: ProjectLockInputField
) -> tuple[str, ...]:
    if value is None:
        return ()
    table = _table(value, reason, field)
    names = tuple(_normalized_lock_name(key, field) for key in table)
    if len(set(names)) != len(names):
        _fail(ProjectLockInputErrorReason.AMBIGUOUS_SELECTION, field)
    for dependency_list in table.values():
        if type(dependency_list) is not list:
            _fail(reason, field)
    return tuple(sorted(names))


def _named_project_requirement_keys(
    value: object, reason: ProjectLockInputErrorReason, field: ProjectLockInputField
) -> tuple[str, ...]:
    names = _named_table_keys(value, reason, field)
    if value is not None:
        for requirements in cast(dict[str, object], value).values():
            if type(requirements) is not list or any(
                type(requirement) is not str for requirement in requirements
            ):
                _fail(reason, field)
    return names


def _table(
    value: object, reason: ProjectLockInputErrorReason, field: ProjectLockInputField
) -> dict[str, object]:
    if type(value) is not dict:
        _fail(reason, field)
    return cast(dict[str, object], value)


def _closed_table(
    table: dict[str, object],
    allowed_keys: frozenset[str],
    reason: ProjectLockInputErrorReason,
    field: ProjectLockInputField,
) -> None:
    if any(type(key) is not str or key not in allowed_keys for key in table):
        _fail(reason, field)


def _normalized_lock_name(value: object, field: ProjectLockInputField) -> str:
    if type(value) is not str:
        _fail(ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field)
    try:
        return normalize_distribution_name(value)
    except (TypeError, ValueError):
        _fail(ProjectLockInputErrorReason.UNSUPPORTED_PROJECT_LOCK, field)


def _normalized_project_name(value: object, field: ProjectLockInputField) -> str:
    if type(value) is not str:
        _fail(ProjectLockInputErrorReason.INVALID_PROJECT, field)
    try:
        return normalize_distribution_name(value)
    except (TypeError, ValueError):
        _fail(ProjectLockInputErrorReason.INVALID_PROJECT, field)


def _fail(
    reason: ProjectLockInputErrorReason, field: ProjectLockInputField
) -> NoReturn:
    raise ProjectLockInputError(reason, field)

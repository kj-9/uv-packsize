"""Read-only discovery for an already installed Python prefix.

This module deliberately treats a prefix as inventory input, rather than as a
Python environment to execute.  It never probes an interpreter, guesses
resolver settings, or performs a case-sensitivity write probe.  The caller
therefore supplies the target path semantics explicitly and observations that
cannot be obtained safely remain ``None``.

The returned layouts are internal, trusted scan handles: they retain physical
paths so inventory can subsequently read the selected tree.  They are not a
result model or JSON payload and are deliberately omitted from ``repr``.  This
is best-effort filesystem validation, not a descriptor snapshot: a concurrent
tree change during discovery or later inventory scanning cannot be prevented.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

from uv_packsize.inventory import (
    InventoryLayout,
    InventoryScanError,
    validated_inventory_layouts,
)
from uv_packsize.models import CaseRule, ExistingPrefixContext, PathFlavor

_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class ExistingPrefixDiscoveryErrorCode(str, Enum):
    """Stable, non-sensitive failures from existing-prefix discovery."""

    HOST_PATH_FLAVOR_MISMATCH = "host-path-flavor-mismatch"
    INVALID_PREFIX = "invalid-prefix"
    INVALID_SITE_PACKAGES = "invalid-site-packages"
    SITE_PACKAGES_NOT_FOUND = "site-packages-not-found"
    SITE_PACKAGES_NOT_DIRECTORY = "site-packages-not-directory"
    SYMLINK_NOT_ALLOWED = "symlink-not-allowed"
    DUPLICATE_SITE_PACKAGES = "duplicate-site-packages"
    LAYOUT_MISMATCH = "layout-mismatch"
    FILESYSTEM_ERROR = "filesystem-error"


class ExistingPrefixDiscoveryError(ValueError):
    """A sanitized discovery failure with a fixed target token only."""

    def __init__(self, code: ExistingPrefixDiscoveryErrorCode, target: str):
        self.code = code
        self.target = target
        super().__init__(f"{code.value}: {target}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExistingPrefixEnvironment:
    """Safe observed context plus internal trusted layouts for one prefix.

    ``layouts`` intentionally remains available to the in-process inventory
    boundary, but its physical paths are omitted from ``repr`` and must never
    be serialized as an analysis result.
    """

    context: ExistingPrefixContext
    layouts: tuple[InventoryLayout, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, ExistingPrefixContext):
            raise TypeError("context must be an ExistingPrefixContext")
        if isinstance(self.layouts, InventoryLayout):
            raise TypeError(
                "layouts must be a non-empty tuple of InventoryLayout values"
            )
        layouts = tuple(self.layouts)
        if not layouts or any(
            not isinstance(layout, InventoryLayout) for layout in layouts
        ):
            raise TypeError(
                "layouts must be a non-empty tuple of InventoryLayout values"
            )
        if any(
            layout.path_flavor is not self.context.path_flavor
            or layout.case_rule is not self.context.case_rule
            for layout in layouts
        ):
            raise ValueError("layouts must match the context path semantics")
        object.__setattr__(self, "layouts", validated_inventory_layouts(layouts))


def discover_existing_prefix(
    *,
    prefix: Path,
    site_packages_relative: tuple[str, ...],
    path_flavor: PathFlavor,
    case_rule: CaseRule,
) -> ExistingPrefixEnvironment:
    """Describe existing site-packages directories without changing the prefix.

    Only the host's native path syntax is meaningful for physical filesystem
    access.  A cross-platform target must be collected on that target rather
    than interpreted through the host's ``Path`` implementation.
    """

    if not isinstance(path_flavor, PathFlavor):
        raise TypeError("path_flavor must be a PathFlavor")
    if not isinstance(case_rule, CaseRule):
        raise TypeError("case_rule must be a CaseRule")
    if path_flavor is not _host_path_flavor():
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.HOST_PATH_FLAVOR_MISMATCH,
            "path-flavor",
        )

    if not isinstance(prefix, Path):
        raise TypeError("prefix must be a Path")
    # Relative Paths are intentionally accepted relative to the current
    # working directory, then fixed to a canonical target before any site
    # discovery.  A final lexical symlink is rejected before this resolution;
    # an ancestor symlink is acceptable and no longer retained in layouts.
    lexical_prefix = Path(os.path.abspath(prefix))
    physical_prefix = _canonical_prefix(lexical_prefix)
    relative_sites = _validated_site_relatives(site_packages_relative, path_flavor)

    layouts: list[InventoryLayout] = []
    for relative in relative_sites:
        site = _validated_site_directory(physical_prefix, relative)
        try:
            layouts.append(
                InventoryLayout(
                    physical_prefix=physical_prefix,
                    physical_site_packages=site,
                    logical_prefix=str(physical_prefix),
                    logical_site_packages=str(site),
                    path_flavor=path_flavor,
                    case_rule=case_rule,
                )
            )
        except (OSError, ValueError) as error:
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.LAYOUT_MISMATCH,
                "site-packages",
            ) from error

    try:
        ordered_layouts = validated_inventory_layouts(tuple(layouts))
    except InventoryScanError as error:
        code = (
            ExistingPrefixDiscoveryErrorCode.DUPLICATE_SITE_PACKAGES
            if error.code.value == "duplicate-site-packages"
            else ExistingPrefixDiscoveryErrorCode.LAYOUT_MISMATCH
        )
        raise ExistingPrefixDiscoveryError(code, "site-packages") from error
    except OSError as error:
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.FILESYSTEM_ERROR,
            "site-packages",
        ) from error

    return ExistingPrefixEnvironment(
        context=ExistingPrefixContext(path_flavor=path_flavor, case_rule=case_rule),
        layouts=ordered_layouts,
    )


def _host_path_flavor() -> PathFlavor:
    return PathFlavor.WINDOWS if os.name == "nt" else PathFlavor.POSIX


def _canonical_prefix(prefix: Path) -> Path:
    try:
        prefix_status = prefix.lstat()
    except FileNotFoundError as error:
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.INVALID_PREFIX,
            "measurement-prefix",
        ) from error
    except OSError as error:
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.FILESYSTEM_ERROR,
            "measurement-prefix",
        ) from error
    if stat.S_ISLNK(prefix_status.st_mode) or not stat.S_ISDIR(prefix_status.st_mode):
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.INVALID_PREFIX,
            "measurement-prefix",
        )
    try:
        return prefix.resolve(strict=True)
    except OSError as error:
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.FILESYSTEM_ERROR,
            "measurement-prefix",
        ) from error


def _validated_site_relatives(
    values: tuple[str, ...], flavor: PathFlavor
) -> tuple[tuple[str, ...], ...]:
    if isinstance(values, str):
        raise TypeError("site_packages_relative must be a tuple of strings")
    try:
        raw_values = tuple(values)
    except TypeError as error:
        raise TypeError("site_packages_relative must be a tuple of strings") from error
    if not raw_values:
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES,
            "site-packages",
        )
    parts = tuple(_relative_parts(value, flavor) for value in raw_values)
    keys = tuple(_site_key(item, flavor) for item in parts)
    if len(set(keys)) != len(keys):
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.DUPLICATE_SITE_PACKAGES,
            "site-packages",
        )
    return parts


def _relative_parts(value: object, flavor: PathFlavor) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES,
            "site-packages",
        )
    path: PurePath
    if flavor is PathFlavor.POSIX:
        if "\\" in value or any(
            component in {"", ".", ".."} for component in value.split("/")
        ):
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES,
                "site-packages",
            )
        path = PurePosixPath(value)
    else:
        if "/" in value or any(
            component in {"", ".", ".."} for component in value.split("\\")
        ):
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES,
                "site-packages",
            )
        path = PureWindowsPath(value)
        if any(not _is_valid_windows_component(component) for component in path.parts):
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES,
                "site-packages",
            )
    if (
        path.is_absolute()
        or path.anchor
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.INVALID_SITE_PACKAGES,
            "site-packages",
        )
    return tuple(path.parts)


def _is_valid_windows_component(component: str) -> bool:
    """Return whether one native Windows relative-path component is safe."""

    return not (
        component.endswith((".", " "))
        or any(character in '<>:"|?*' or ord(character) < 32 for character in component)
        or component.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_NAMES
    )


def _site_key(parts: tuple[str, ...], flavor: PathFlavor) -> tuple[str, ...]:
    # Before touching the filesystem, literal duplicates are always aliases.
    # Filesystem/case-rule aliases are also caught by validated_inventory_layouts.
    return tuple(parts)


def _validated_site_directory(prefix: Path, parts: tuple[str, ...]) -> Path:
    try:
        resolved_prefix = prefix.resolve(strict=True)
    except OSError as error:
        raise ExistingPrefixDiscoveryError(
            ExistingPrefixDiscoveryErrorCode.FILESYSTEM_ERROR,
            "measurement-prefix",
        ) from error
    current = prefix
    for part in parts:
        current = current / part
        try:
            entry = current.lstat()
        except FileNotFoundError as error:
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.SITE_PACKAGES_NOT_FOUND,
                "site-packages",
            ) from error
        except OSError as error:
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.FILESYSTEM_ERROR,
                "site-packages",
            ) from error
        if stat.S_ISLNK(entry.st_mode):
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.SYMLINK_NOT_ALLOWED,
                "site-packages",
            )
        if not stat.S_ISDIR(entry.st_mode):
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.SITE_PACKAGES_NOT_DIRECTORY,
                "site-packages",
            )
        try:
            current.relative_to(prefix)
            current.resolve(strict=True).relative_to(resolved_prefix)
        except ValueError as error:
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.LAYOUT_MISMATCH,
                "site-packages",
            ) from error
        except OSError as error:
            raise ExistingPrefixDiscoveryError(
                ExistingPrefixDiscoveryErrorCode.FILESYSTEM_ERROR,
                "site-packages",
            ) from error
    return current

"""Discover the immutable measurement description of one temporary venv.

This adapter intentionally does not create a virtual environment, invoke
``uv``, collect inventory, or render output.  Its one subprocess operation is
an execution of the venv's Python interpreter, which reports the target
environment's own prefix and sysconfig locations in one JSON payload.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from uv_packsize.inventory import InventoryLayout
from uv_packsize.models import BuildPolicy, CaseRule, PathFlavor, ResolutionContext

_PROBE_SCRIPT = """
import json
import os
import platform
import sys
import sysconfig

print(json.dumps({
    "prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "executable": sys.executable,
    "python_version": platform.python_version(),
    "sysconfig_platform": sysconfig.get_platform(),
    "machine": platform.machine(),
    "os_name": os.name,
    "purelib": sysconfig.get_path("purelib"),
    "platlib": sysconfig.get_path("platlib"),
}))
"""
_NUMERIC_PYTHON_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class EnvironmentDiscoveryErrorCode(str, Enum):
    """Stable, sanitized failures from temporary-environment discovery."""

    INVALID_VENV = "invalid-venv"
    PROBE_FAILED = "probe-failed"
    INVALID_PROBE = "invalid-probe"
    LAYOUT_MISMATCH = "layout-mismatch"
    CASE_RULE_MISMATCH = "case-rule-mismatch"
    FILESYSTEM_ERROR = "filesystem-error"


class EnvironmentDiscoveryError(ValueError):
    """A discovery failure that never includes a path or requirement value."""

    def __init__(self, code: EnvironmentDiscoveryErrorCode, target: str):
        self.code = code
        self.target = target
        super().__init__(f"{code.value}: {target}")


@dataclass(frozen=True, slots=True, kw_only=True)
class VenvProbe:
    """The complete, single-process report emitted by a venv interpreter."""

    prefix: str
    base_prefix: str
    executable: str
    python_version: str
    sysconfig_platform: str
    machine: str
    os_name: str
    purelib: str
    platlib: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> VenvProbe:
        field_names = (
            "prefix",
            "base_prefix",
            "executable",
            "python_version",
            "sysconfig_platform",
            "machine",
            "os_name",
            "purelib",
            "platlib",
        )
        try:
            probe_values = {name: values[name] for name in field_names}
        except (KeyError, TypeError) as error:
            raise EnvironmentDiscoveryError(
                EnvironmentDiscoveryErrorCode.INVALID_PROBE,
                "python-probe",
            ) from error
        if any(
            not isinstance(value, str) or not value.strip() or "\0" in value
            for value in probe_values.values()
        ) or not _NUMERIC_PYTHON_VERSION.fullmatch(
            _probe_string(probe_values["python_version"])
        ):
            raise EnvironmentDiscoveryError(
                EnvironmentDiscoveryErrorCode.INVALID_PROBE,
                "python-probe",
            )
        return cls(
            prefix=_probe_string(probe_values["prefix"]),
            base_prefix=_probe_string(probe_values["base_prefix"]),
            executable=_probe_string(probe_values["executable"]),
            python_version=_probe_string(probe_values["python_version"]),
            sysconfig_platform=_probe_string(probe_values["sysconfig_platform"]),
            machine=_probe_string(probe_values["machine"]),
            os_name=_probe_string(probe_values["os_name"]),
            purelib=_probe_string(probe_values["purelib"]),
            platlib=_probe_string(probe_values["platlib"]),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class InstalledEnvironment:
    """Immutable context and compatible site-packages layouts for one venv."""

    context: ResolutionContext
    layouts: tuple[InventoryLayout, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.context, ResolutionContext):
            raise TypeError("context must be a ResolutionContext")
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
        object.__setattr__(self, "layouts", layouts)


ProbeRunner = Callable[[Path, str], subprocess.CompletedProcess[bytes]]
CaseRuleProbe = Callable[[Path], CaseRule]


def _probe_string(value: object) -> str:
    """Narrow a VenvProbe field after ``from_mapping`` has validated it."""

    if not isinstance(value, str):
        raise AssertionError("validated probe field must be a string")
    return value


def discover_installed_environment(  # noqa: PLR0913
    *,
    venv_path: Path,
    requirements: tuple[str, ...],
    uv_version: str,
    build_policy: BuildPolicy,
    compile_bytecode: bool,
    extras: tuple[str, ...] = (),
    index_identifiers: tuple[str, ...] = (),
    resolution_strategy: str = "highest",
    venv_python: Path | None = None,
    probe_runner: ProbeRunner | None = None,
    case_rule_probe: CaseRuleProbe | None = None,
) -> InstalledEnvironment:
    """Describe an already-created temporary venv without installing anything.

    Caller-supplied resolution settings are passed directly into
    :class:`ResolutionContext`; this function never derives them from the host
    environment.  ``venv_python`` and the two probe callables are injection
    points for focused tests, not a second source of environment metadata.
    """

    physical_prefix = Path(os.path.abspath(venv_path))
    python = venv_python or _default_venv_python(physical_prefix)
    probe = _probe_venv_python(python, probe_runner or _run_probe)
    _validate_venv_identity(
        expected_prefix=physical_prefix,
        invoked_python=python,
        probe=probe,
    )

    purelib = Path(probe.purelib)
    platlib = Path(probe.platlib)
    _validate_site_paths(
        physical_prefix=physical_prefix,
        sites=(purelib, platlib),
    )
    case_probe = case_rule_probe or detect_case_rule
    try:
        purelib_case_rule = case_probe(purelib)
        platlib_case_rule = case_probe(platlib)
    except EnvironmentDiscoveryError:
        raise
    except (OSError, ValueError) as error:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.FILESYSTEM_ERROR,
            "site-packages",
        ) from error

    return build_installed_environment(
        probe=probe,
        physical_prefix=physical_prefix,
        physical_purelib=purelib,
        physical_platlib=platlib,
        purelib_case_rule=purelib_case_rule,
        platlib_case_rule=platlib_case_rule,
        requirements=requirements,
        uv_version=uv_version,
        build_policy=build_policy,
        compile_bytecode=compile_bytecode,
        extras=extras,
        index_identifiers=index_identifiers,
        resolution_strategy=resolution_strategy,
    )


def build_installed_environment(  # noqa: PLR0913
    *,
    probe: VenvProbe,
    physical_prefix: Path,
    physical_purelib: Path,
    physical_platlib: Path,
    purelib_case_rule: CaseRule,
    platlib_case_rule: CaseRule,
    requirements: tuple[str, ...],
    uv_version: str,
    build_policy: BuildPolicy,
    compile_bytecode: bool,
    extras: tuple[str, ...] = (),
    index_identifiers: tuple[str, ...] = (),
    resolution_strategy: str = "highest",
) -> InstalledEnvironment:
    """Purely build an installed-environment value from one verified probe.

    ``physical_*`` deliberately remains separate from the probe's logical
    paths.  That lets platform layout tests build a Windows logical venv on a
    POSIX test filesystem without relying on the host's path rules.
    """

    if not isinstance(probe, VenvProbe):
        raise TypeError("probe must be a VenvProbe")
    if purelib_case_rule is not platlib_case_rule:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.CASE_RULE_MISMATCH,
            "site-packages",
        )
    if not isinstance(purelib_case_rule, CaseRule):
        raise TypeError("site package case rules must be CaseRule values")

    path_flavor = _path_flavor(probe.os_name)
    try:
        layouts = _deduplicated_layouts(
            (
                InventoryLayout(
                    physical_prefix=physical_prefix,
                    physical_site_packages=physical_purelib,
                    logical_prefix=probe.prefix,
                    logical_site_packages=probe.purelib,
                    path_flavor=path_flavor,
                    case_rule=purelib_case_rule,
                ),
                InventoryLayout(
                    physical_prefix=physical_prefix,
                    physical_site_packages=physical_platlib,
                    logical_prefix=probe.prefix,
                    logical_site_packages=probe.platlib,
                    path_flavor=path_flavor,
                    case_rule=platlib_case_rule,
                ),
            )
        )
    except (OSError, ValueError) as error:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.LAYOUT_MISMATCH,
            "site-packages",
        ) from error
    context = ResolutionContext(
        requirements=requirements,
        python_version=probe.python_version,
        platform=probe.sysconfig_platform,
        architecture=probe.machine,
        path_flavor=path_flavor,
        case_rule=purelib_case_rule,
        uv_version=uv_version,
        build_policy=build_policy,
        compile_bytecode=compile_bytecode,
        extras=extras,
        index_identifiers=index_identifiers,
        resolution_strategy=resolution_strategy,
    )
    return InstalledEnvironment(context=context, layouts=layouts)


def detect_case_rule(site_packages: Path) -> CaseRule:
    """Probe one site-packages directory and always remove the probe directory."""

    site_packages = Path(site_packages)
    probe_name = f"uv_packsize_case_probe_{uuid.uuid4().hex}"
    probe_directory = site_packages / probe_name
    alternate = site_packages / probe_name.upper()
    created = False
    probe_error: OSError | None = None
    try:
        probe_directory.mkdir()
        created = True
        return CaseRule.INSENSITIVE if alternate.exists() else CaseRule.SENSITIVE
    except OSError as error:
        probe_error = error
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.FILESYSTEM_ERROR,
            "site-packages",
        ) from error
    finally:
        if created:
            try:
                probe_directory.rmdir()
            except OSError as cleanup_error:
                if probe_error is None:
                    raise EnvironmentDiscoveryError(
                        EnvironmentDiscoveryErrorCode.FILESYSTEM_ERROR,
                        "site-packages",
                    ) from cleanup_error


def _default_venv_python(physical_prefix: Path) -> Path:
    candidates = (
        (physical_prefix / "Scripts" / "python.exe", physical_prefix / "bin" / "python")
        if os.name == "nt"
        else (
            physical_prefix / "bin" / "python",
            physical_prefix / "Scripts" / "python.exe",
        )
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise EnvironmentDiscoveryError(
        EnvironmentDiscoveryErrorCode.INVALID_VENV,
        "temporary-environment",
    )


def _run_probe(python: Path, script: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [str(python), "-I", "-c", script],
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.PROBE_FAILED,
            "python-probe",
        ) from error


def _probe_venv_python(python: Path, runner: ProbeRunner) -> VenvProbe:
    try:
        completed = runner(python, _PROBE_SCRIPT)
    except EnvironmentDiscoveryError:
        raise
    except (OSError, ValueError) as error:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.PROBE_FAILED,
            "python-probe",
        ) from error
    if completed.returncode != 0:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.PROBE_FAILED,
            "python-probe",
        )
    try:
        decoded = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.INVALID_PROBE,
            "python-probe",
        ) from error
    if not isinstance(decoded, dict):
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.INVALID_PROBE,
            "python-probe",
        )
    return VenvProbe.from_mapping(decoded)


def _validate_venv_identity(
    *,
    expected_prefix: Path,
    invoked_python: Path,
    probe: VenvProbe,
) -> None:
    try:
        expected_resolved = expected_prefix.resolve(strict=True)
        reported_prefix = Path(probe.prefix)
        if reported_prefix.resolve(strict=True) != expected_resolved:
            raise ValueError("prefix differs")
        if Path(probe.base_prefix).resolve(strict=False) == expected_resolved:
            raise ValueError("base prefix matches")
        expected_prefix_absolute = Path(os.path.abspath(expected_prefix))
        reported_prefix_absolute = Path(os.path.abspath(probe.prefix))
        reported_executable = Path(os.path.abspath(probe.executable))
        invoked_executable = Path(os.path.abspath(invoked_python))
        reported_executable.relative_to(reported_prefix_absolute)
        invoked_executable.relative_to(expected_prefix_absolute)
        if not invoked_executable.samefile(reported_executable):
            raise ValueError("interpreter differs")
    except (OSError, ValueError) as error:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.INVALID_VENV,
            "temporary-environment",
        ) from error


def _path_flavor(os_name: str) -> PathFlavor:
    if os_name == "nt":
        return PathFlavor.WINDOWS
    if os_name == "posix":
        return PathFlavor.POSIX
    raise EnvironmentDiscoveryError(
        EnvironmentDiscoveryErrorCode.INVALID_PROBE,
        "python-probe",
    )


def _validate_site_paths(*, physical_prefix: Path, sites: tuple[Path, Path]) -> None:
    try:
        resolved_prefix = physical_prefix.resolve(strict=True)
        for site in sites:
            site.resolve(strict=True).relative_to(resolved_prefix)
    except (OSError, ValueError) as error:
        raise EnvironmentDiscoveryError(
            EnvironmentDiscoveryErrorCode.INVALID_VENV,
            "temporary-environment",
        ) from error


def _deduplicated_layouts(
    layouts: tuple[InventoryLayout, InventoryLayout],
) -> tuple[InventoryLayout, ...]:
    deduplicated: list[InventoryLayout] = []
    physical_sites: dict[Path, tuple[str, tuple[str, ...]]] = {}
    logical_sites: dict[tuple[str, tuple[str, ...]], Path] = {}
    for layout in layouts:
        physical_site = layout.physical_site_packages.resolve(strict=False)
        anchor, parts = layout.normalized_logical_site_packages
        if layout.case_rule is CaseRule.INSENSITIVE:
            logical_site = (anchor.casefold(), tuple(part.casefold() for part in parts))
        else:
            logical_site = (anchor, parts)
        duplicate_physical_site = physical_site in physical_sites
        duplicate_logical_site = logical_site in logical_sites
        previous_logical = physical_sites.setdefault(physical_site, logical_site)
        previous_physical = logical_sites.setdefault(logical_site, physical_site)
        if previous_logical != logical_site or previous_physical != physical_site:
            raise ValueError("site package layouts disagree")
        if not duplicate_physical_site and not duplicate_logical_site:
            deduplicated.append(layout)
    return tuple(deduplicated)

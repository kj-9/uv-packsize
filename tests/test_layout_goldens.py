"""Host-independent golden coverage for supported installed layouts."""

from __future__ import annotations

import csv
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from local_wheel_factory import build_wheelhouse

from uv_packsize.analysis import analyze_installed_environment
from uv_packsize.inventory import CaseRule, InventoryLayout, PathFlavor
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import BuildPolicy, ResolutionContext
from uv_packsize.render import render_analysis_report

_GOLDEN_DIRECTORY = Path(__file__).parent / "golden" / "layouts"
_ROOT_A = "uv-packsize-fixture-root-a"
_REQUIREMENTS = (f"{_ROOT_A}==1.0.0",)


@dataclass(frozen=True, slots=True)
class TargetLayout:
    name: str
    logical_prefix: str
    site_packages_relative: str
    scripts_relative: str
    headers_relative: str
    platform: str
    architecture: str
    path_flavor: PathFlavor
    case_rule: CaseRule

    @property
    def logical_site_packages(self) -> str:
        separator = "\\" if self.path_flavor is PathFlavor.WINDOWS else "/"
        return separator.join((self.logical_prefix, self.site_packages_relative))


_TARGET_LAYOUTS = (
    TargetLayout(
        name="linux",
        logical_prefix="/opt/uv-packsize/venv",
        site_packages_relative="lib/python3.13/site-packages",
        scripts_relative="bin",
        headers_relative="include/python3.13",
        platform="manylinux_2_28_x86_64",
        architecture="x86_64",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    ),
    TargetLayout(
        name="macos",
        logical_prefix="/Applications/uv-packsize/venv",
        site_packages_relative="lib/python3.13/site-packages",
        scripts_relative="bin",
        headers_relative="include/python3.13",
        platform="macosx_14_0_arm64",
        architecture="aarch64",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    ),
    TargetLayout(
        name="windows",
        logical_prefix=r"C:\uv-packsize\venv",
        site_packages_relative="Lib/site-packages",
        scripts_relative="Scripts",
        headers_relative="Include",
        platform="win_amd64",
        architecture="x86_64",
        path_flavor=PathFlavor.WINDOWS,
        case_rule=CaseRule.INSENSITIVE,
    ),
)


@pytest.mark.parametrize("target", _TARGET_LAYOUTS, ids=lambda target: target.name)
def test_layout_inventory_and_renderers_match_golden(
    tmp_path: Path, target: TargetLayout
):
    """Inventory real fixture-wheel contents under each target's logical layout."""

    layout = _create_layout(tmp_path, target)
    wheelhouse = tmp_path / "wheelhouse"
    _install_wheel_contents(layout, target, build_wheelhouse(wheelhouse)[_ROOT_A])

    result = analyze_installed_environment(
        context=ResolutionContext(
            requirements=_REQUIREMENTS,
            python_version="3.13.2",
            platform=target.platform,
            architecture=target.architecture,
            path_flavor=target.path_flavor,
            case_rule=target.case_rule,
            uv_version="0.11.3",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=False,
        ),
        layouts=(layout,),
    )

    expected_json = _golden(target, "json")
    expected_document = json.loads(expected_json)
    assert (
        result.total_logical_bytes
        == expected_document["totals"]["global_logical_bytes"]
    )
    assert (
        sum(distribution.total_logical_bytes for distribution in result.distributions)
        == expected_document["totals"]["distribution_logical_bytes"]
    )
    assert render_analysis_report(result, show_scripts=True) == _golden(target, "txt")
    assert render_analysis_json(result) == expected_json


def _create_layout(tmp_path: Path, target: TargetLayout) -> InventoryLayout:
    prefix = tmp_path / target.name / "venv"
    site_packages = prefix.joinpath(*target.site_packages_relative.split("/"))
    site_packages.mkdir(parents=True)
    return InventoryLayout(
        physical_prefix=prefix,
        physical_site_packages=site_packages,
        logical_prefix=target.logical_prefix,
        logical_site_packages=target.logical_site_packages,
        path_flavor=target.path_flavor,
        case_rule=target.case_rule,
    )


def _install_wheel_contents(
    layout: InventoryLayout,
    target: TargetLayout,
    wheel: Path,
) -> None:
    """Materialize wheel payloads using the target's installation schemes.

    This deliberately stops before host-specific entry point generation.  The
    P2-06a integration test owns real installer execution; this test fixes the
    inventory contract for the platform layout paths it receives.
    """

    with zipfile.ZipFile(wheel) as archive:
        members = [
            member for member in archive.namelist() if not member.endswith("/RECORD")
        ]
        dist_info = next(
            member.split("/", maxsplit=1)[0]
            for member in members
            if ".dist-info/" in member
        )
        record_rows: list[tuple[str, str, str]] = []
        for member in members:
            physical_path, record_path = _installed_path(
                layout,
                target,
                member,
            )
            physical_path.parent.mkdir(parents=True, exist_ok=True)
            physical_path.write_bytes(archive.read(member))
            record_rows.append((record_path, "", ""))

    record_rows.append((f"{dist_info}/RECORD", "", ""))
    record_path = layout.physical_site_packages / dist_info / "RECORD"
    with record_path.open("w", encoding="utf-8", newline="") as record_file:
        csv.writer(record_file).writerows(record_rows)


def _installed_path(
    layout: InventoryLayout,
    target: TargetLayout,
    member: str,
) -> tuple[Path, str]:
    data_prefix, marker, scheme_path = member.partition(".data/")
    if not marker:
        return layout.physical_site_packages / member, member

    del data_prefix
    scheme, separator, payload = scheme_path.partition("/")
    assert separator
    if scheme == "scripts":
        relative = f"{target.scripts_relative}/{payload}"
    elif scheme == "data":
        relative = payload
    elif scheme == "headers":
        relative = f"{target.headers_relative}/{payload}"
    else:  # pragma: no cover - the shared deterministic fixture defines its schemes.
        raise AssertionError(f"unsupported wheel data scheme: {scheme}")
    return (
        layout.physical_prefix.joinpath(*relative.split("/")),
        _absolute_record_path(target, relative),
    )


def _absolute_record_path(target: TargetLayout, relative: str) -> str:
    if target.path_flavor is PathFlavor.WINDOWS:
        windows_relative = relative.replace("/", "\\")
        return f"{target.logical_prefix}\\{windows_relative}"
    return f"{target.logical_prefix}/{relative}"


def _golden(target: TargetLayout, suffix: str) -> str:
    golden = (_GOLDEN_DIRECTORY / f"{target.name}.{suffix}").read_text()
    return golden.removesuffix("\n") if suffix == "txt" else golden

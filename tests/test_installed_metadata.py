from pathlib import Path

import pytest

from uv_packsize.dependency_graph import (
    DependencyGraphCompleteness,
    DependencyGraphWarningCode,
    DependencyKind,
    MarkerEnvironment,
)
from uv_packsize.environment import InstalledEnvironment
from uv_packsize.installed_metadata import (
    InstalledMetadataAdapterError,
    InstalledMetadataAdapterErrorCode,
    build_installed_dependency_graph,
)
from uv_packsize.inventory import (
    InventoryLayout,
    InventoryScanError,
    InventoryScanErrorCode,
)
from uv_packsize.json_render import render_analysis_json
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    PathFlavor,
    ResolutionContext,
)


def marker_environment() -> MarkerEnvironment:
    return MarkerEnvironment(
        implementation_name="cpython",
        implementation_version="3.12.4",
        os_name="posix",
        platform_machine="x86_64",
        platform_python_implementation="CPython",
        platform_release="6.8",
        platform_system="Linux",
        platform_version="#1",
        python_full_version="3.12.4",
        python_version="3.12",
        sys_platform="linux",
    )


def analysis(*names: str) -> AnalysisResult:
    requirements = (
        tuple(name for name in ("root-a", "root-b") if name in names) or names
    )
    return AnalysisResult(
        context=ResolutionContext(
            requirements=requirements,
            python_version="3.12.4",
            platform="linux",
            architecture="x86_64",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
            uv_version="test",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=False,
        ),
        distributions=tuple(
            DistributionResult(name=name, version="1", files=()) for name in names
        ),
    )


def environment(
    result: AnalysisResult,
    *layouts: InventoryLayout,
) -> InstalledEnvironment:
    return InstalledEnvironment(
        context=result.context,
        layouts=layouts,
        marker_environment=marker_environment(),
    )


def layout(tmp_path: Path, name: str = "purelib") -> InventoryLayout:
    prefix = tmp_path / "venv"
    site_packages = prefix / "lib" / name / "site-packages"
    site_packages.mkdir(parents=True)
    return InventoryLayout(
        physical_prefix=prefix,
        physical_site_packages=site_packages,
        logical_prefix="/opt/venv",
        logical_site_packages=f"/opt/venv/lib/{name}/site-packages",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    )


def write_metadata(
    inventory_layout: InventoryLayout,
    name: str,
    *,
    version: str = "1",
    requires_dist: tuple[str, ...] = (),
    directory_name: str | None = None,
) -> Path:
    dist_info = inventory_layout.physical_site_packages / (
        directory_name or f"{name}-{version}.dist-info"
    )
    dist_info.mkdir()
    metadata = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
    metadata.extend(f"Requires-Dist: {value}" for value in requires_dist)
    (dist_info / "METADATA").write_text("\n".join(metadata) + "\n", encoding="utf-8")
    return dist_info


def test_adapter_reads_direct_child_metadata_and_builds_shared_graph(tmp_path):
    purelib = layout(tmp_path, "purelib")
    platlib = layout(tmp_path, "platlib")
    write_metadata(purelib, "root-a", requires_dist=("shared",))
    write_metadata(platlib, "root-b", requires_dist=("shared",))
    write_metadata(purelib, "shared")
    nested = purelib.physical_site_packages / "nested" / "ignored-1.dist-info"
    nested.mkdir(parents=True)
    (nested / "METADATA").write_text("Name: ignored\nVersion: 1\n")

    result = analysis("root-a", "root-b", "shared")
    graph = build_installed_dependency_graph(
        result,
        environment(result, platlib, purelib),
    )

    assert [(edge.source_name, edge.target_name) for edge in graph.edges] == [
        ("root-a", "shared"),
        ("root-b", "shared"),
    ]
    assert [(node.name, node.kind, node.is_shared) for node in graph.nodes] == [
        ("root-a", DependencyKind.ROOT, False),
        ("root-b", DependencyKind.ROOT, False),
        ("shared", DependencyKind.DIRECT, True),
    ]
    assert graph.warnings == ()


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        (None, DependencyGraphWarningCode.MISSING_METADATA),
        (b"Name: root\nVersion: 1\n\xff", DependencyGraphWarningCode.INVALID_METADATA),
        (
            b"Name: root\nVersion: 1\nMalformed Header\n",
            DependencyGraphWarningCode.INVALID_METADATA,
        ),
    ],
)
def test_adapter_converts_missing_and_invalid_metadata_to_safe_warnings(
    tmp_path, contents, expected
):
    inventory_layout = layout(tmp_path)
    dist_info = inventory_layout.physical_site_packages / "root-1.dist-info"
    dist_info.mkdir()
    if contents is not None:
        (dist_info / "METADATA").write_bytes(contents)

    result = analysis("root")
    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert [(warning.code, warning.target_identity) for warning in graph.warnings] == [
        (expected, "root")
    ]


@pytest.mark.parametrize(
    "metadata_version_headers",
    [
        (),
        ("Metadata-Version: two.one",),
        ("Metadata-Version: 2",),
        ("Metadata-Version: 2.1.0",),
        ("Metadata-Version: 0.0",),
        ("Metadata-Version: 1.3",),
        ("Metadata-Version: 2.0",),
        ("Metadata-Version: 2.6",),
        ("Metadata-Version: 99.42",),
        ("Metadata-Version: 2.1", "Metadata-Version: 2.2"),
    ],
)
def test_adapter_rejects_missing_duplicate_or_unsupported_core_metadata_version(
    tmp_path, metadata_version_headers
):
    inventory_layout = layout(tmp_path)
    dist_info = inventory_layout.physical_site_packages / "root-1.dist-info"
    dist_info.mkdir()
    headers = (*metadata_version_headers, "Name: root", "Version: 1")
    (dist_info / "METADATA").write_text("\n".join(headers) + "\n")
    result = analysis("root")

    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert [(warning.code, warning.target_identity) for warning in graph.warnings] == [
        (DependencyGraphWarningCode.INVALID_METADATA, "root")
    ]
    assert graph.completeness is DependencyGraphCompleteness.INCOMPLETE


@pytest.mark.parametrize(
    "metadata_version",
    ("1.0", "1.1", "1.2", "2.1", "2.2", "2.3", "2.4", "2.5"),
)
def test_adapter_accepts_each_legal_core_metadata_version(tmp_path, metadata_version):
    inventory_layout = layout(tmp_path)
    dist_info = inventory_layout.physical_site_packages / "root-1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: {metadata_version}\nName: root\nVersion: 1\n"
    )
    result = analysis("root")

    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert graph.warnings == ()


@pytest.mark.parametrize(
    "identity_headers",
    [
        ("Version: 1",),
        ("Name: root",),
        ("Name: root", "Name: other", "Version: 1"),
        ("Name: root", "Version: 1", "Version: 2"),
    ],
)
def test_adapter_requires_exactly_one_name_and_version_header(
    tmp_path, identity_headers
):
    inventory_layout = layout(tmp_path)
    dist_info = inventory_layout.physical_site_packages / "root-1.dist-info"
    dist_info.mkdir()
    headers = ("Metadata-Version: 2.1", *identity_headers)
    (dist_info / "METADATA").write_text("\n".join(headers) + "\n")
    result = analysis("root")

    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert [(warning.code, warning.target_identity) for warning in graph.warnings] == [
        (DependencyGraphWarningCode.INVALID_METADATA, "root")
    ]


@pytest.mark.parametrize("kind", ["directory", "metadata"])
def test_adapter_does_not_follow_dist_info_or_metadata_symlinks(tmp_path, kind):
    inventory_layout = layout(tmp_path)
    dist_info = inventory_layout.physical_site_packages / "root-1.dist-info"
    if kind == "directory":
        target = tmp_path / "outside-root-1.dist-info"
        target.mkdir()
        (target / "METADATA").write_text("Name: root\nVersion: 1\n")
        dist_info.symlink_to(target, target_is_directory=True)
    else:
        dist_info.mkdir()
        target = tmp_path / "outside-metadata"
        target.write_text("Name: root\nVersion: 1\n")
        (dist_info / "METADATA").symlink_to(target)

    result = analysis("root")
    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert graph.warnings[0].code is DependencyGraphWarningCode.INVALID_METADATA
    assert graph.warnings[0].target_identity == "root"


def test_adapter_rejects_nonregular_metadata_file(tmp_path):
    inventory_layout = layout(tmp_path)
    dist_info = inventory_layout.physical_site_packages / "root-1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").mkdir()

    result = analysis("root")
    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert graph.warnings[0].code is DependencyGraphWarningCode.INVALID_METADATA


def test_adapter_converts_unreadable_metadata_to_a_safe_warning(tmp_path, monkeypatch):
    inventory_layout = layout(tmp_path)
    dist_info = write_metadata(inventory_layout, "root")
    metadata_path = dist_info / "METADATA"
    original_lstat = Path.lstat

    def unreadable(path: Path):
        if path == metadata_path:
            raise PermissionError("private filesystem detail")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", unreadable)
    result = analysis("root")
    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert [(warning.code, warning.target_identity) for warning in graph.warnings] == [
        (DependencyGraphWarningCode.INVALID_METADATA, "root")
    ]
    assert "private filesystem detail" not in repr(graph)


@pytest.mark.parametrize(
    ("name", "version", "expected"),
    [
        ("child", "1", DependencyGraphWarningCode.METADATA_NAME_MISMATCH),
        ("root", "2", DependencyGraphWarningCode.METADATA_VERSION_MISMATCH),
    ],
)
def test_adapter_reports_metadata_identity_mismatches_without_using_it(
    tmp_path, name, version, expected
):
    inventory_layout = layout(tmp_path)
    write_metadata(
        inventory_layout,
        name,
        version=version,
        directory_name="root-1.dist-info",
    )

    result = analysis("root")
    graph = build_installed_dependency_graph(
        result,
        environment(result, inventory_layout),
    )

    assert [(warning.code, warning.target_identity) for warning in graph.warnings] == [
        (expected, "root")
    ]
    assert graph.edges == ()


def test_adapter_reports_duplicate_distributions_across_purelib_and_platlib(tmp_path):
    purelib = layout(tmp_path, "purelib")
    platlib = layout(tmp_path, "platlib")
    write_metadata(purelib, "root")
    write_metadata(platlib, "root")

    result = analysis("root")
    graph = build_installed_dependency_graph(
        result,
        environment(result, purelib, platlib),
    )

    assert [(warning.code, warning.target_identity) for warning in graph.warnings] == [
        (DependencyGraphWarningCode.DUPLICATE_METADATA, "root")
    ]


def test_adapter_reuses_inventory_duplicate_site_and_incompatible_layout_errors(
    tmp_path,
):
    first = layout(tmp_path, "first")
    duplicate = InventoryLayout(
        physical_prefix=first.physical_prefix,
        physical_site_packages=first.physical_site_packages,
        logical_prefix=first.logical_prefix,
        logical_site_packages=first.logical_site_packages,
        path_flavor=first.path_flavor,
        case_rule=first.case_rule,
    )
    incompatible = InventoryLayout(
        physical_prefix=first.physical_prefix,
        physical_site_packages=first.physical_prefix / "other" / "site-packages",
        logical_prefix="/different",
        logical_site_packages="/different/other/site-packages",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    )
    incompatible.physical_site_packages.mkdir(parents=True)
    result = analysis("root")

    with pytest.raises(InventoryScanError) as duplicate_error:
        build_installed_dependency_graph(
            result,
            environment(result, first, duplicate),
        )
    with pytest.raises(InventoryScanError) as incompatible_error:
        build_installed_dependency_graph(
            result,
            environment(result, first, incompatible),
        )

    assert duplicate_error.value.code is InventoryScanErrorCode.DUPLICATE_SITE_PACKAGES
    assert incompatible_error.value.code is InventoryScanErrorCode.INCOMPATIBLE_LAYOUT


def test_adapter_rejects_analysis_from_a_different_environment_context(tmp_path):
    inventory_layout = layout(tmp_path)
    write_metadata(inventory_layout, "root")
    result = analysis("root")
    different_result = analysis("root-a")
    installed = environment(different_result, inventory_layout)

    with pytest.raises(InstalledMetadataAdapterError) as error:
        build_installed_dependency_graph(result, installed)

    assert error.value.code is InstalledMetadataAdapterErrorCode.CONTEXT_MISMATCH
    assert error.value.target == "installed-environment"
    assert str(error.value) == "context-mismatch: installed-environment"


def test_adapter_is_permutation_stable_and_does_not_mutate_analysis_or_leak_secrets(
    tmp_path,
):
    purelib = layout(tmp_path, "purelib")
    platlib = layout(tmp_path, "platlib")
    secret = "https://token@private.invalid/hidden?key=secret"
    write_metadata(purelib, "root-a", requires_dist=("shared",))
    root_b = write_metadata(platlib, "root-b")
    (root_b / "METADATA").write_bytes(
        f"Name: root-b\nVersion: 1\nRequires-Dist: child @ {secret}\n".encode()
        + b"\xff"
    )
    write_metadata(purelib, "shared")
    result = analysis("shared", "root-b", "root-a")
    before = render_analysis_json(result)

    forward = build_installed_dependency_graph(
        result,
        environment(result, purelib, platlib),
    )
    reverse = build_installed_dependency_graph(
        result,
        environment(result, platlib, purelib),
    )

    assert forward == reverse
    assert render_analysis_json(result) == before
    rendered = repr(forward)
    assert secret not in rendered
    assert "token@" not in rendered
    assert "Malformed" not in rendered
    assert {
        (warning.code, warning.target_identity) for warning in forward.warnings
    } == {(DependencyGraphWarningCode.INVALID_METADATA, "root-b")}

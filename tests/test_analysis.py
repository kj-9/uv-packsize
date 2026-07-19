import csv
from pathlib import Path
from typing import Any, cast

import pytest

import uv_packsize.analysis as analysis_module
from uv_packsize.analysis import (
    AnalysisContextError,
    AnalysisContextErrorCode,
    analyze_installed_environment,
)
from uv_packsize.inventory import (
    CaseRule,
    InventoryConflictError,
    InventoryConflictErrorCode,
    InventoryLayout,
    InventoryScanError,
    InventoryScanErrorCode,
    PathFlavor,
    SupplementalErrorCode,
    SupplementalInventoryError,
    SupplementalOwnership,
)
from uv_packsize.models import (
    BuildPolicy,
    Completeness,
    FileOrigin,
    ResolutionContext,
    WarningCode,
)


def context(**overrides: Any) -> ResolutionContext:
    values: dict[str, Any] = {
        "requirements": ("example",),
        "python_version": "3.12.4",
        "platform": "linux",
        "architecture": "x86_64",
        "path_flavor": PathFlavor.POSIX,
        "case_rule": CaseRule.SENSITIVE,
        "uv_version": "0.11.3",
        "build_policy": BuildPolicy.WHEEL_ONLY,
        "compile_bytecode": True,
    }
    values.update(overrides)
    return ResolutionContext(**values)


def layout(tmp_path: Path, python_version: str = "3.12") -> InventoryLayout:
    prefix = tmp_path / "venv"
    site_packages = prefix / "lib" / f"python{python_version}" / "site-packages"
    site_packages.mkdir(parents=True)
    return InventoryLayout(
        physical_prefix=prefix,
        physical_site_packages=site_packages,
        logical_prefix="/opt/venv",
        logical_site_packages=(f"/opt/venv/lib/python{python_version}/site-packages"),
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    )


def install_distribution(
    inventory_layout: InventoryLayout,
    *,
    name: str,
    version: str,
    record_paths: tuple[str, ...] | None = None,
) -> Path:
    dist_info = inventory_layout.physical_site_packages / f"{name}-{version}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )
    paths = record_paths or (f"{name}.py",)
    for record_path in paths:
        if record_path.startswith("../../../"):
            physical = inventory_layout.physical_prefix / record_path.removeprefix(
                "../../../"
            )
        else:
            physical = inventory_layout.physical_site_packages / record_path
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_bytes(name.encode())
    rows = [(path, "", "") for path in paths]
    rows.append((f"{dist_info.name}/RECORD", "", ""))
    with (dist_info / "RECORD").open("w", newline="") as record:
        csv.writer(record).writerows(rows)
    return dist_info


def test_analysis_preserves_context_and_resolved_versions(tmp_path):
    inventory_layout = layout(tmp_path)
    install_distribution(
        inventory_layout,
        name="Example_Pkg",
        version="2.4",
    )
    resolution = context(
        requirements=("Example_Pkg>=2",),
        python_version="3.13.1",
        platform="custom-linux-target",
        architecture="aarch64",
        uv_version="0.12.0",
        build_policy=BuildPolicy.ALLOW_BUILD,
        compile_bytecode=False,
        extras=("speedups",),
        index_identifiers=("internal",),
        resolution_strategy="lowest-direct",
    )

    result = analyze_installed_environment(
        context=resolution,
        layouts=(inventory_layout,),
    )

    assert result.context is resolution
    assert result.context == resolution
    assert [(item.name, item.version) for item in result.distributions] == [
        ("example-pkg", "2.4")
    ]


def test_analysis_is_deterministic_for_layout_and_supplemental_order(tmp_path):
    first = layout(tmp_path, "3.12")
    second = layout(tmp_path, "3.13")
    install_distribution(first, name="z_pkg", version="1")
    install_distribution(second, name="a_pkg", version="2")
    tool = first.physical_prefix / "bin" / "tool"
    tool.parent.mkdir()
    tool.write_bytes(b"tool")
    first_ownership = SupplementalOwnership(
        distribution_name="z_pkg",
        distribution_version="1",
        paths=("bin/tool",),
    )
    duplicate_ownership = SupplementalOwnership(
        distribution_name="z-pkg",
        distribution_version="1",
        paths=("bin/tool",),
    )
    resolution = context(requirements=("z_pkg", "a_pkg"))

    forward = analyze_installed_environment(
        context=resolution,
        layouts=(first, second),
        supplemental=(first_ownership, duplicate_ownership),
    )
    reverse = analyze_installed_environment(
        context=resolution,
        layouts=(second, first),
        supplemental=(duplicate_ownership, first_ownership),
    )

    assert forward == reverse
    assert hash(forward) == hash(reverse)
    assert [item.name for item in forward.distributions] == ["a-pkg", "z-pkg"]
    assert (
        sum(
            file.origin is FileOrigin.DISCOVERED
            for distribution in forward.distributions
            for file in distribution.files
        )
        == 1
    )


def test_empty_installed_environment_is_complete(tmp_path):
    inventory_layout = layout(tmp_path)

    result = analyze_installed_environment(
        context=context(),
        layouts=(inventory_layout,),
    )

    assert result.distributions == ()
    assert result.total_logical_bytes == 0
    assert result.warnings == ()
    assert result.completeness is Completeness.COMPLETE


def test_analysis_derives_global_shared_ownership_once(tmp_path):
    inventory_layout = layout(tmp_path)
    install_distribution(
        inventory_layout,
        name="first",
        version="1",
        record_paths=("../../../bin/shared",),
    )
    install_distribution(inventory_layout, name="second", version="2")
    supplemental = SupplementalOwnership(
        distribution_name="second",
        distribution_version="2",
        paths=("bin/shared",),
    )

    result = analyze_installed_environment(
        context=context(requirements=("first", "second")),
        layouts=(inventory_layout,),
        supplemental=(supplemental,),
    )

    unique_total = sum(
        {
            file.canonical_identity: file.logical_bytes
            for distribution in result.distributions
            for file in distribution.files
        }.values()
    )
    assert result.total_logical_bytes == unique_total
    assert (
        sum(distribution.total_logical_bytes for distribution in result.distributions)
        > result.total_logical_bytes
    )
    assert [warning.code for warning in result.warnings] == [
        WarningCode.DUPLICATE_OWNERSHIP
    ]
    assert result.duplicate_ownerships[0].owners == ("first", "second")


def test_distribution_incompleteness_propagates_to_analysis(tmp_path):
    inventory_layout = layout(tmp_path)
    dist_info = install_distribution(
        inventory_layout,
        name="example",
        version="1",
    )
    (dist_info / "RECORD").unlink()

    result = analyze_installed_environment(
        context=context(),
        layouts=(inventory_layout,),
    )

    assert result.distributions[0].completeness is Completeness.INCOMPLETE
    assert result.completeness is Completeness.INCOMPLETE
    assert WarningCode.MISSING_RECORD in {
        warning.code for warning in result.distributions[0].warnings
    }
    assert result.warnings == ()


def test_context_does_not_filter_observed_generated_files(tmp_path):
    inventory_layout = layout(tmp_path)
    install_distribution(
        inventory_layout,
        name="example",
        version="1",
    )
    bytecode = (
        inventory_layout.physical_site_packages
        / "__pycache__"
        / "example.cpython-312.pyc"
    )
    bytecode.parent.mkdir()
    bytecode.write_bytes(b"bytecode")
    resolution = context(compile_bytecode=False)

    result = analyze_installed_environment(
        context=resolution,
        layouts=(inventory_layout,),
    )

    assert result.context.compile_bytecode is False
    assert any(
        file.origin is FileOrigin.GENERATED for file in result.distributions[0].files
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"context": object()}, "context"),
        ({"layouts": ()}, "layouts"),
        ({"layouts": object()}, "layouts"),
        ({"supplemental": object()}, "supplemental"),
    ],
)
def test_analysis_validates_context_and_collections(tmp_path, overrides, message):
    values: dict[str, Any] = {
        "context": context(),
        "layouts": (layout(tmp_path),),
    }
    values.update(overrides)

    with pytest.raises(TypeError, match=message):
        analyze_installed_environment(**values)


def test_analysis_rejects_single_collection_values(tmp_path):
    inventory_layout = layout(tmp_path)
    ownership = SupplementalOwnership(
        distribution_name="example",
        distribution_version="1",
        paths=("bin/tool",),
    )

    with pytest.raises(TypeError, match="layouts"):
        analyze_installed_environment(
            context=context(),
            layouts=cast(Any, inventory_layout),
        )
    with pytest.raises(TypeError, match="supplemental"):
        analyze_installed_environment(
            context=context(),
            layouts=(inventory_layout,),
            supplemental=cast(Any, ownership),
        )


@pytest.mark.parametrize(
    ("resolution", "expected_code"),
    [
        (
            context(path_flavor=PathFlavor.WINDOWS),
            AnalysisContextErrorCode.PATH_FLAVOR_MISMATCH,
        ),
        (
            context(case_rule=CaseRule.INSENSITIVE),
            AnalysisContextErrorCode.CASE_RULE_MISMATCH,
        ),
    ],
)
def test_context_layout_mismatch_is_typed_and_precedes_scan(
    tmp_path, monkeypatch, resolution, expected_code
):
    inventory_layout = layout(tmp_path)

    def unexpected_collection(*, layouts, supplemental):
        del layouts, supplemental
        raise AssertionError("filesystem inventory must not run")

    monkeypatch.setattr(
        analysis_module,
        "collect_distributions",
        unexpected_collection,
    )

    with pytest.raises(AnalysisContextError) as error:
        analyze_installed_environment(
            context=resolution,
            layouts=(inventory_layout,),
        )

    assert error.value.code is expected_code
    assert error.value.target == "inventory-layout"


def test_analysis_calls_collector_once_with_materialized_collections(
    tmp_path, monkeypatch
):
    inventory_layout = layout(tmp_path)
    calls = []

    def collect_once(*, layouts, supplemental):
        calls.append((layouts, supplemental))
        return ()

    monkeypatch.setattr(analysis_module, "collect_distributions", collect_once)

    result = analyze_installed_environment(
        context=context(),
        layouts=(item for item in (inventory_layout,)),
        supplemental=(item for item in ()),
    )

    assert result.distributions == ()
    assert calls == [((inventory_layout,), ())]


@pytest.mark.parametrize(
    "error",
    [
        InventoryScanError(
            InventoryScanErrorCode.FILESYSTEM_ERROR,
            "site-packages",
        ),
        SupplementalInventoryError(
            SupplementalErrorCode.MISSING_FILE,
            "bin/tool",
        ),
        InventoryConflictError(
            InventoryConflictErrorCode.FILE_SIGNATURE,
            "shared",
        ),
    ],
)
def test_analysis_propagates_inventory_errors_unchanged(tmp_path, monkeypatch, error):
    inventory_layout = layout(tmp_path)

    def fail_collection(*, layouts, supplemental):
        del layouts, supplemental
        raise error

    monkeypatch.setattr(analysis_module, "collect_distributions", fail_collection)

    with pytest.raises(type(error)) as raised:
        analyze_installed_environment(
            context=context(),
            layouts=(inventory_layout,),
        )

    assert raised.value is error

import csv
import os
from pathlib import Path
from typing import Any, cast

import pytest

import uv_packsize.inventory as inventory_module
from uv_packsize.inventory import (
    CaseRule,
    InvalidRecordPathError,
    InventoryConflictError,
    InventoryConflictErrorCode,
    InventoryError,
    InventoryLayout,
    InventoryScanError,
    InventoryScanErrorCode,
    PathFlavor,
    RecordPathOutsidePrefixError,
    SupplementalErrorCode,
    SupplementalInventoryError,
    SupplementalOwnership,
    collect_distribution,
    collect_distributions,
    resolve_record_path,
    resolve_supplemental_path,
)
from uv_packsize.models import (
    AnalysisResult,
    BuildPolicy,
    Completeness,
    DistributionResult,
    FileCategory,
    FileEntry,
    FileOrigin,
    ResolutionContext,
    WarningCode,
)


def write_metadata(
    dist_info: Path, name: str = "Example_Pkg", version: str = "1"
) -> None:
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )


def write_record(
    dist_info: Path,
    rows: list[tuple[str, str, str]],
    *,
    include_self: bool = True,
) -> None:
    rows = list(rows)
    if include_self:
        rows.append((f"{dist_info.name}/RECORD", "", ""))
    with (dist_info / "RECORD").open("w", encoding="utf-8", newline="") as record:
        csv.writer(record).writerows(rows)


def without_record_file(result: DistributionResult):
    return tuple(
        entry
        for entry in result.files
        if not entry.path.casefold().endswith(".dist-info/record")
    )


def posix_layout(tmp_path: Path) -> tuple[InventoryLayout, Path]:
    prefix = tmp_path / "venv"
    site_packages = prefix / "lib" / "python3.12" / "site-packages"
    dist_info = site_packages / "Example-1.dist-info"
    dist_info.mkdir(parents=True)
    return (
        InventoryLayout(
            physical_prefix=prefix,
            physical_site_packages=site_packages,
            logical_prefix="/opt/venv",
            logical_site_packages="/opt/venv/lib/python3.12/site-packages",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
        ),
        dist_info,
    )


def windows_layout(tmp_path: Path) -> tuple[InventoryLayout, Path]:
    prefix = tmp_path / "venv"
    site_packages = prefix / "Lib" / "site-packages"
    dist_info = site_packages / "Example-1.dist-info"
    dist_info.mkdir(parents=True)
    return (
        InventoryLayout(
            physical_prefix=prefix,
            physical_site_packages=site_packages,
            logical_prefix=r"C:\venv",
            logical_site_packages=r"C:\venv\Lib\site-packages",
            path_flavor=PathFlavor.WINDOWS,
            case_rule=CaseRule.INSENSITIVE,
        ),
        dist_info,
    )


def second_posix_layout(layout: InventoryLayout) -> InventoryLayout:
    site_packages = layout.physical_prefix / "lib" / "python3.13" / "site-packages"
    site_packages.mkdir(parents=True)
    return InventoryLayout(
        physical_prefix=layout.physical_prefix,
        physical_site_packages=site_packages,
        logical_prefix=layout.logical_prefix,
        logical_site_packages="/opt/venv/lib/python3.13/site-packages",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    )


def install_distribution(
    layout: InventoryLayout,
    *,
    name: str,
    version: str = "1",
    filename: str | None = None,
) -> tuple[Path, Path]:
    dist_info = layout.physical_site_packages / f"{name}-{version}.dist-info"
    dist_info.mkdir()
    write_metadata(dist_info, name=name, version=version)
    owned = layout.physical_site_packages / (filename or f"{name}.py")
    owned.write_bytes(name.encode())
    write_record(dist_info, [(owned.name, "", "")])
    return dist_info, owned


@pytest.mark.parametrize(
    ("record_path", "expected"),
    [
        ("example/__init__.py", "lib/python3.12/site-packages/example/__init__.py"),
        ("../../../bin/example", "bin/example"),
        ("/opt/venv/include/example.h", "include/example.h"),
    ],
)
def test_resolve_posix_record_paths(tmp_path, record_path, expected):
    layout, dist_info = posix_layout(tmp_path)

    resolved = resolve_record_path(
        layout=layout,
        dist_info_dir=dist_info,
        record_path=record_path,
    )

    assert resolved.path == expected
    assert resolved.canonical_identity == expected
    assert resolved.physical_path == layout.physical_prefix.joinpath(
        *expected.split("/")
    )


@pytest.mark.parametrize(
    "record_path",
    [
        "../../../../outside",
        "/opt/venv-sibling/file",
        "/outside/file",
    ],
)
def test_resolve_posix_rejects_paths_outside_prefix(tmp_path, record_path):
    layout, dist_info = posix_layout(tmp_path)

    with pytest.raises(RecordPathOutsidePrefixError):
        resolve_record_path(
            layout=layout,
            dist_info_dir=dist_info,
            record_path=record_path,
        )


def test_resolve_posix_rejects_root_underflow(tmp_path):
    layout, dist_info = posix_layout(tmp_path)

    with pytest.raises(InvalidRecordPathError, match="underflows"):
        resolve_record_path(
            layout=layout,
            dist_info_dir=dist_info,
            record_path="../../../../../../../../file",
        )


@pytest.mark.parametrize(
    ("record_path", "expected"),
    [
        (r"example\Module.py", "Lib/site-packages/example/Module.py"),
        ("example/Module.py", "Lib/site-packages/example/Module.py"),
        (r"..\..\Scripts\Tool.EXE", "Scripts/Tool.EXE"),
        (r"C:\venv\Include\Example.h", "Include/Example.h"),
    ],
)
def test_resolve_windows_record_paths_and_casefolds_identity(
    tmp_path, record_path, expected
):
    layout, dist_info = windows_layout(tmp_path)

    resolved = resolve_record_path(
        layout=layout,
        dist_info_dir=dist_info,
        record_path=record_path,
    )

    assert resolved.path == expected
    assert resolved.canonical_identity == expected.casefold()


def test_windows_resolver_maps_case_insensitively_to_existing_physical_path(tmp_path):
    layout, dist_info = windows_layout(tmp_path)
    physical_file = layout.physical_site_packages / "Example" / "Module.py"
    physical_file.parent.mkdir()
    physical_file.write_text("value = 1")

    resolved = resolve_record_path(
        layout=layout,
        dist_info_dir=dist_info,
        record_path=r"C:\VENV\lib\SITE-PACKAGES\example\module.PY",
    )

    assert resolved.physical_path == physical_file
    assert resolved.path == "lib/SITE-PACKAGES/example/module.PY"
    assert resolved.canonical_identity == "lib/site-packages/example/module.py"


@pytest.mark.parametrize(
    "record_path",
    [
        r"D:\venv\file",
        r"\\server\share\file",
        r"C:\venv-sibling\file",
    ],
)
def test_resolve_windows_rejects_absolute_paths_outside_prefix(tmp_path, record_path):
    layout, dist_info = windows_layout(tmp_path)

    with pytest.raises(RecordPathOutsidePrefixError):
        resolve_record_path(
            layout=layout,
            dist_info_dir=dist_info,
            record_path=record_path,
        )


@pytest.mark.parametrize("record_path", [r"\rooted", r"C:drive-relative"])
def test_resolve_windows_rejects_ambiguous_paths(tmp_path, record_path):
    layout, dist_info = windows_layout(tmp_path)

    with pytest.raises(InvalidRecordPathError):
        resolve_record_path(
            layout=layout,
            dist_info_dir=dist_info,
            record_path=record_path,
        )


@pytest.mark.parametrize(
    "record_path",
    [
        "file. ",
        "file.",
        "name:stream",
        "bad?.py",
        "CON",
        "nul.txt",
        "control\x01.py",
    ],
)
def test_resolve_windows_rejects_win32_alias_and_invalid_components(
    tmp_path, record_path
):
    layout, dist_info = windows_layout(tmp_path)

    with pytest.raises(InvalidRecordPathError, match="Windows component"):
        resolve_record_path(
            layout=layout,
            dist_info_dir=dist_info,
            record_path=record_path,
        )


def test_resolve_windows_unc_layout_host_independently(tmp_path):
    prefix = tmp_path / "venv"
    site_packages = prefix / "Lib" / "site-packages"
    dist_info = site_packages / "Example-1.dist-info"
    dist_info.mkdir(parents=True)
    layout = InventoryLayout(
        physical_prefix=prefix,
        physical_site_packages=site_packages,
        logical_prefix=r"\\server\share\venv",
        logical_site_packages=r"\\server\share\venv\Lib\site-packages",
        path_flavor=PathFlavor.WINDOWS,
        case_rule=CaseRule.INSENSITIVE,
    )

    relative = resolve_record_path(
        layout=layout,
        dist_info_dir=dist_info,
        record_path=r"..\..\Scripts\tool.exe",
    )
    absolute = resolve_record_path(
        layout=layout,
        dist_info_dir=dist_info,
        record_path=r"\\SERVER\SHARE\VENV\include\header.h",
    )

    assert relative.canonical_identity == "scripts/tool.exe"
    assert absolute.canonical_identity == "include/header.h"
    with pytest.raises(RecordPathOutsidePrefixError):
        resolve_record_path(
            layout=layout,
            dist_info_dir=dist_info,
            record_path=r"\\server\other\venv\file",
        )


def test_resolver_requires_dist_info_directly_under_site_packages(tmp_path):
    layout, _dist_info = posix_layout(tmp_path)
    nested = layout.physical_site_packages / "nested" / "Example-1.dist-info"

    with pytest.raises(ValueError, match="directly inside"):
        resolve_record_path(
            layout=layout,
            dist_info_dir=nested,
            record_path="example.py",
        )


def test_collects_record_files_outside_site_packages_and_generated_bytecode(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    source = layout.physical_site_packages / "example" / "module.py"
    bytecode = source.parent / "__pycache__" / "module.cpython-312.pyc"
    script = layout.physical_prefix / "bin" / "example"
    header = layout.physical_prefix / "include" / "example.h"
    for path, content in (
        (source, b"source"),
        (bytecode, b"bytecode"),
        (script, b"script"),
        (header, b"header"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    write_record(
        dist_info,
        [
            ("example/module.py", "", ""),
            ("../../../bin/example", "", ""),
            ("/opt/venv/include/example.h", "", ""),
        ],
    )

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert result.name == "example-pkg"
    assert result.version == "1"
    assert result.total_logical_bytes == sum(
        path.stat().st_size
        for path in (source, bytecode, script, header, dist_info / "RECORD")
    )
    by_path = {entry.path: entry for entry in result.files}
    assert (
        by_path["lib/python3.12/site-packages/example/module.py"].origin
        is FileOrigin.RECORD
    )
    assert (
        by_path[
            "lib/python3.12/site-packages/example/__pycache__/module.cpython-312.pyc"
        ].origin
        is FileOrigin.GENERATED
    )
    assert by_path["bin/example"].category is FileCategory.SCRIPT
    assert by_path["include/example.h"].category is FileCategory.DATA
    assert result.completeness is Completeness.COMPLETE


def test_explicit_record_bytecode_stays_record(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    source = layout.physical_site_packages / "example.py"
    bytecode = layout.physical_site_packages / "__pycache__" / "example.cpython-312.pyc"
    source.write_bytes(b"source")
    bytecode.parent.mkdir()
    bytecode.write_bytes(b"bytecode")
    write_record(
        dist_info,
        [("example.py", "", ""), ("__pycache__/example.cpython-312.pyc", "", "")],
    )

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert {entry.origin for entry in result.files} == {FileOrigin.RECORD}


def test_missing_file_and_duplicate_record_entry_are_typed_warnings(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    write_record(
        dist_info,
        [("missing.py", "", ""), ("missing.py", "sha256=abc_def", "0")],
    )

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert without_record_file(result) == ()
    assert {warning.code for warning in result.warnings} == {
        WarningCode.DUPLICATE_RECORD_ENTRY,
        WarningCode.MISSING_FILE,
    }
    assert result.completeness is Completeness.INCOMPLETE


def test_record_csv_quoted_path_is_collected(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    quoted_file = layout.physical_site_packages / "data,part.csv"
    quoted_file.write_bytes(b"value")
    write_record(dist_info, [("data,part.csv", "sha256=abc_def", "5")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert [entry.path for entry in without_record_file(result)] == [
        "lib/python3.12/site-packages/data,part.csv"
    ]
    assert without_record_file(result)[0].category is FileCategory.DATA


@pytest.mark.parametrize(
    "record_bytes",
    [
        b'"unterminated,,\n',
        b"only,two\n",
        b",hash,size\n",
        b"bad-utf8,hash,size\xff\n",
        b"example.py,not-a-hash,1\n",
        b"example.py,sha256=abc,NaN\n",
        b"example.py,sha256=abc,-1\n",
        "example.py,sha256=abc,１２\n".encode(),
    ],
)
def test_invalid_record_is_incomplete_without_fallback(tmp_path, record_bytes):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    (dist_info / "RECORD").write_bytes(record_bytes)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert result.files == ()
    assert [warning.code for warning in result.warnings] == [WarningCode.INVALID_RECORD]
    assert result.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("dangling", [False, True])
def test_record_symlink_is_invalid_and_never_followed(tmp_path, dangling):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    external_record = tmp_path / "external-record"
    if not dangling:
        external_record.write_text("example.py,,\n")
        (layout.physical_site_packages / "example.py").write_bytes(b"must not be read")
    (dist_info / "RECORD").symlink_to(external_record)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert result.files == ()
    assert [warning.code for warning in result.warnings] == [WarningCode.INVALID_RECORD]


def test_invalid_and_outside_paths_are_deduplicated_distribution_warnings(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    write_record(
        dist_info,
        [
            ("bad\\path", "", ""),
            ("another\\bad", "", ""),
            ("/outside/one", "", ""),
            ("/outside/two", "", ""),
        ],
    )

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert [warning.code for warning in result.warnings] == [
        WarningCode.INVALID_RECORD_PATH,
        WarningCode.RECORD_PATH_OUTSIDE_PREFIX,
    ]
    assert all(
        warning.target_identity == "example-pkg==1" for warning in result.warnings
    )
    assert result.completeness is Completeness.INCOMPLETE


def test_missing_record_falls_back_only_to_dist_info_subtree(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    (dist_info / "INSTALLER").write_bytes(b"uv")
    unrelated = layout.physical_site_packages / "example.py"
    unrelated.write_bytes(b"not owned by conservative fallback")

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert {entry.path for entry in result.files} == {
        "lib/python3.12/site-packages/Example-1.dist-info/INSTALLER",
        "lib/python3.12/site-packages/Example-1.dist-info/METADATA",
    }
    assert {entry.origin for entry in result.files} == {FileOrigin.FALLBACK}
    assert [warning.code for warning in result.warnings] == [WarningCode.MISSING_RECORD]
    assert result.completeness is Completeness.INCOMPLETE


def test_fallback_counts_final_directory_symlink_without_traversing_it(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    outside = tmp_path / "fallback-outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"must not be collected")
    link = dist_info / "external-data"
    link.symlink_to(outside, target_is_directory=True)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    by_name = {Path(entry.path).name: entry for entry in result.files}
    assert "external-data" in by_name
    assert "secret" not in by_name
    assert by_name["external-data"].logical_bytes == link.lstat().st_size
    assert by_name["external-data"].symlink_target == os.readlink(link)


def test_fallback_skips_real_directories_and_collects_nested_files(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    nested = dist_info / "licenses"
    nested.mkdir()
    license_file = nested / "LICENSE"
    license_file.write_bytes(b"license")

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert any(entry.path.endswith("/licenses/LICENSE") for entry in result.files)
    assert [warning.code for warning in result.warnings] == [WarningCode.MISSING_RECORD]


def test_final_symlink_uses_link_lstat_size_and_does_not_follow_target(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    outside = tmp_path / "outside-secret"
    outside.write_bytes(b"secret target bytes")
    link = layout.physical_site_packages / "example-link"
    link.symlink_to(outside)
    write_record(dist_info, [("example-link", "", "")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert len(without_record_file(result)) == 1
    entry = without_record_file(result)[0]
    assert entry.logical_bytes == link.lstat().st_size
    assert entry.logical_bytes != outside.stat().st_size
    assert entry.symlink_target == os.readlink(link)


def test_intermediate_symlink_escape_is_rejected_without_reading_target(
    tmp_path, monkeypatch
):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"secret")
    (layout.physical_site_packages / "package").symlink_to(
        outside, target_is_directory=True
    )
    write_record(dist_info, [("package/secret", "", "")])

    original_iterdir = Path.iterdir

    def guarded_iterdir(path):
        if path == outside:
            raise AssertionError("outside directory must not be enumerated")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert without_record_file(result) == ()
    assert [warning.code for warning in result.warnings] == [
        WarningCode.RECORD_PATH_OUTSIDE_PREFIX
    ]


def test_zero_byte_and_hardlinked_paths_are_counted_by_lexical_path(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    first = layout.physical_site_packages / "first.dat"
    second = layout.physical_site_packages / "second.dat"
    empty = layout.physical_site_packages / "empty.dat"
    first.write_bytes(b"content")
    os.link(first, second)
    empty.write_bytes(b"")
    write_record(
        dist_info,
        [("first.dat", "", ""), ("second.dat", "", ""), ("empty.dat", "", "")],
    )

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert len(without_record_file(result)) == 3
    assert (
        result.total_logical_bytes
        == len(b"content") * 2 + (dist_info / "RECORD").stat().st_size
    )


def test_windows_case_collision_is_one_file_with_duplicate_warning(tmp_path):
    layout, dist_info = windows_layout(tmp_path)
    write_metadata(dist_info)
    file = layout.physical_site_packages / "Example.py"
    file.write_bytes(b"content")
    write_record(dist_info, [("Example.py", "", ""), ("example.PY", "", "")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert len(without_record_file(result)) == 1
    assert (
        without_record_file(result)[0].canonical_identity
        == "lib/site-packages/example.py"
    )
    assert [warning.code for warning in result.warnings] == [
        WarningCode.DUPLICATE_RECORD_ENTRY
    ]


def test_windows_uppercase_python_source_generates_bytecode(tmp_path):
    layout, dist_info = windows_layout(tmp_path)
    write_metadata(dist_info)
    source = layout.physical_site_packages / "Example.PY"
    bytecode = layout.physical_site_packages / "__PYCACHE__" / "Example.cpython-312.PYC"
    source.write_bytes(b"source")
    bytecode.parent.mkdir()
    bytecode.write_bytes(b"bytecode")
    write_record(dist_info, [("example.py", "", "")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert {entry.origin for entry in result.files} == {
        FileOrigin.RECORD,
        FileOrigin.GENERATED,
    }


def test_symlink_target_is_preserved_raw_even_with_surrounding_spaces(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    target = " target "
    link = layout.physical_site_packages / "spaced-link"
    link.symlink_to(target)
    write_record(dist_info, [("spaced-link", "", "")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert without_record_file(result)[0].symlink_target == target


def test_posix_record_path_preserves_whitespace_filename(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    file = layout.physical_site_packages / " file "
    file.write_bytes(b"content")
    write_record(dist_info, [(" file ", "", "")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert result.files[0].path.endswith("/ file ")


def test_layout_rejects_site_packages_symlink_escape(tmp_path):
    prefix = tmp_path / "venv"
    prefix.mkdir()
    outside = tmp_path / "outside-site"
    outside.mkdir()
    site_packages = prefix / "site-packages"
    site_packages.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="must not escape"):
        InventoryLayout(
            physical_prefix=prefix,
            physical_site_packages=site_packages,
            logical_prefix="/venv",
            logical_site_packages="/venv/site-packages",
            path_flavor=PathFlavor.POSIX,
            case_rule=CaseRule.SENSITIVE,
        )


def test_collect_distribution_rejects_symlinked_dist_info(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    outside = tmp_path / "outside-dist-info"
    outside.mkdir()
    dist_info.rmdir()
    dist_info.symlink_to(outside, target_is_directory=True)

    with pytest.raises(InventoryError, match="real directory"):
        collect_distribution(layout=layout, dist_info_dir=dist_info)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is not available")
def test_unsupported_special_file_is_typed_incomplete_warning(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    special = layout.physical_site_packages / "special"
    os.mkfifo(special)
    write_record(dist_info, [("special", "", "")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert without_record_file(result) == ()
    assert [warning.code for warning in result.warnings] == [
        WarningCode.UNSUPPORTED_FILE_TYPE
    ]
    assert result.completeness is Completeness.INCOMPLETE


def test_non_missing_filesystem_error_is_typed_incomplete_warning(
    tmp_path, monkeypatch
):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    file = layout.physical_site_packages / "unreadable.py"
    file.write_bytes(b"content")
    write_record(dist_info, [("unreadable.py", "", "")])
    original_lstat = Path.lstat

    def guarded_lstat(path):
        if path == file:
            raise PermissionError("denied")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", guarded_lstat)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert without_record_file(result) == ()
    assert [warning.code for warning in result.warnings] == [
        WarningCode.FILESYSTEM_ERROR
    ]
    assert result.completeness is Completeness.INCOMPLETE


def test_resolver_filesystem_error_is_distribution_typed_warning(tmp_path, monkeypatch):
    layout, dist_info = windows_layout(tmp_path)
    write_metadata(dist_info)
    file = layout.physical_site_packages / "Example.py"
    file.write_bytes(b"content")
    write_record(dist_info, [("Example.py", "", "")])
    original_iterdir = Path.iterdir

    def guarded_iterdir(path):
        if path == layout.physical_site_packages:
            raise PermissionError("denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert result.files == ()
    assert [warning.code for warning in result.warnings] == [
        WarningCode.FILESYSTEM_LAYOUT_ERROR
    ]


def test_record_lstat_error_is_distribution_typed_warning(tmp_path, monkeypatch):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    write_record(dist_info, [("example.py", "", "")])
    record = dist_info / "RECORD"
    original_lstat = Path.lstat

    def guarded_lstat(path):
        if path == record:
            raise PermissionError("denied")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", guarded_lstat)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert result.files == ()
    assert [warning.code for warning in result.warnings] == [
        WarningCode.FILESYSTEM_LAYOUT_ERROR
    ]


def test_generated_bytecode_scan_error_is_file_typed_warning(tmp_path, monkeypatch):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    source = layout.physical_site_packages / "example.py"
    source.write_bytes(b"source")
    cache = layout.physical_site_packages / "__pycache__"
    cache.mkdir()
    write_record(dist_info, [("example.py", "", "")])
    original_iterdir = Path.iterdir

    def guarded_iterdir(path):
        if path == cache:
            raise PermissionError("denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert len(without_record_file(result)) == 1
    assert [warning.code for warning in result.warnings] == [
        WarningCode.FILESYSTEM_ERROR
    ]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is not available")
def test_fallback_special_file_is_not_silently_skipped(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    special = dist_info / "special"
    os.mkfifo(special)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert WarningCode.MISSING_RECORD in {warning.code for warning in result.warnings}
    assert WarningCode.UNSUPPORTED_FILE_TYPE in {
        warning.code for warning in result.warnings
    }
    assert result.completeness is Completeness.INCOMPLETE


def test_collect_distributions_scans_multiple_layouts_deterministically(tmp_path):
    first_layout, original = posix_layout(tmp_path)
    original.rmdir()
    second_layout = second_posix_layout(first_layout)
    install_distribution(first_layout, name="z_pkg")
    install_distribution(second_layout, name="a_pkg")

    forward = collect_distributions(layouts=(first_layout, second_layout))
    reverse = collect_distributions(layouts=(second_layout, first_layout))

    assert forward == reverse
    assert [distribution.name for distribution in forward] == ["a-pkg", "z-pkg"]


def test_scan_sorts_reversed_filesystem_enumeration(tmp_path, monkeypatch):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="z_pkg")
    install_distribution(layout, name="a_pkg")
    expected = collect_distributions(layouts=(layout,))
    original_iterdir = Path.iterdir

    def reversed_iterdir(path):
        children = tuple(original_iterdir(path))
        if path == layout.physical_site_packages:
            return iter(reversed(children))
        return iter(children)

    monkeypatch.setattr(Path, "iterdir", reversed_iterdir)

    assert collect_distributions(layouts=(layout,)) == expected


def test_valid_metadata_does_not_require_parseable_dist_info_name(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    dist_info = layout.physical_site_packages / "opaque.dist-info"
    dist_info.mkdir()
    write_metadata(dist_info, name="Metadata_Name", version="2")
    write_record(dist_info, [])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert (result.name, result.version) == ("metadata-name", "2")
    assert result.warnings == ()


@pytest.mark.parametrize(
    ("metadata_setup", "warning_code"),
    [
        ("missing", WarningCode.MISSING_METADATA),
        ("malformed", WarningCode.INVALID_METADATA),
        ("symlink", WarningCode.INVALID_METADATA),
    ],
)
def test_metadata_fallback_is_typed(tmp_path, metadata_setup, warning_code):
    layout, dist_info = posix_layout(tmp_path)
    if metadata_setup == "malformed":
        (dist_info / "METADATA").write_text("Metadata-Version: 2.1\nName: example\n")
    elif metadata_setup == "symlink":
        target = tmp_path / "metadata"
        target.write_text("Name: external\nVersion: 9\n")
        (dist_info / "METADATA").symlink_to(target)
    write_record(dist_info, [])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert (result.name, result.version) == ("example", "1")
    assert [warning.code for warning in result.warnings] == [warning_code]


def test_unparseable_dist_info_without_valid_metadata_is_rejected(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    dist_info = layout.physical_site_packages / "opaque.dist-info"
    dist_info.mkdir()
    write_record(dist_info, [])

    with pytest.raises(InventoryError, match="name and version"):
        collect_distribution(layout=layout, dist_info_dir=dist_info)


def test_empty_record_is_invalid(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    (dist_info / "RECORD").write_bytes(b"")

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert [warning.code for warning in result.warnings] == [WarningCode.INVALID_RECORD]


def test_nonempty_record_without_self_entry_has_typed_warning(tmp_path):
    layout, dist_info = posix_layout(tmp_path)
    write_metadata(dist_info)
    owned = layout.physical_site_packages / "example.py"
    owned.write_bytes(b"x")
    write_record(dist_info, [("example.py", "", "")], include_self=False)

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert [warning.code for warning in result.warnings] == [
        WarningCode.MISSING_RECORD_SELF_ENTRY
    ]
    assert result.completeness is Completeness.INCOMPLETE


def test_scan_rejects_incompatible_and_duplicate_layouts(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    duplicate = InventoryLayout(
        physical_prefix=layout.physical_prefix,
        physical_site_packages=layout.physical_site_packages,
        logical_prefix=layout.logical_prefix,
        logical_site_packages=layout.logical_site_packages,
        path_flavor=layout.path_flavor,
        case_rule=layout.case_rule,
    )
    incompatible_site = layout.physical_prefix / "other" / "site-packages"
    incompatible_site.mkdir(parents=True)
    incompatible = InventoryLayout(
        physical_prefix=layout.physical_prefix,
        physical_site_packages=incompatible_site,
        logical_prefix="/different",
        logical_site_packages="/different/other/site-packages",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    )

    with pytest.raises(InventoryScanError) as duplicate_error:
        collect_distributions(layouts=(layout, duplicate))
    with pytest.raises(InventoryScanError) as incompatible_error:
        collect_distributions(layouts=(layout, incompatible))

    assert duplicate_error.value.code is InventoryScanErrorCode.DUPLICATE_SITE_PACKAGES
    assert incompatible_error.value.code is InventoryScanErrorCode.INCOMPATIBLE_LAYOUT


def test_scan_rejects_site_packages_symlink_alias_as_duplicate(tmp_path):
    prefix = tmp_path / "venv"
    real_site = prefix / "real-site"
    real_site.mkdir(parents=True)
    alias_site = prefix / "alias-site"
    alias_site.symlink_to(real_site, target_is_directory=True)
    real = InventoryLayout(
        physical_prefix=prefix,
        physical_site_packages=real_site,
        logical_prefix="/opt/venv",
        logical_site_packages="/opt/venv/real-site",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    )
    alias = InventoryLayout(
        physical_prefix=prefix,
        physical_site_packages=alias_site,
        logical_prefix="/opt/venv",
        logical_site_packages="/opt/venv/alias-site",
        path_flavor=PathFlavor.POSIX,
        case_rule=CaseRule.SENSITIVE,
    )

    with pytest.raises(InventoryScanError) as error:
        collect_distributions(layouts=(real, alias))

    assert error.value.code is InventoryScanErrorCode.DUPLICATE_SITE_PACKAGES


@pytest.mark.parametrize(
    ("second_version", "expected_code"),
    [
        ("1", InventoryScanErrorCode.DUPLICATE_DISTRIBUTION),
        ("2", InventoryScanErrorCode.CONFLICTING_DISTRIBUTION_VERSION),
    ],
)
def test_scan_rejects_normalized_distribution_collisions(
    tmp_path, second_version, expected_code
):
    first, original = posix_layout(tmp_path)
    original.rmdir()
    second = second_posix_layout(first)
    install_distribution(first, name="Example_Pkg", version="1")
    install_distribution(second, name="example.pkg", version=second_version)

    with pytest.raises(InventoryScanError) as error:
        collect_distributions(layouts=(second, first))

    assert error.value.code is expected_code
    assert error.value.target == "example-pkg"


def test_windows_scan_accepts_uppercase_dist_info_suffix(tmp_path):
    layout, original = windows_layout(tmp_path)
    original.rmdir()
    dist_info = layout.physical_site_packages / "Example-1.DIST-INFO"
    dist_info.mkdir()
    write_metadata(dist_info)
    write_record(dist_info, [])

    result = collect_distributions(layouts=(layout,))

    assert [(item.name, item.version) for item in result] == [("example-pkg", "1")]


def test_windows_scan_accepts_case_variant_prefix_across_layouts(tmp_path):
    first, original = windows_layout(tmp_path)
    original.rmdir()
    second_site = first.physical_prefix / "Lib" / "alternate"
    second_site.mkdir(parents=True)
    second = InventoryLayout(
        physical_prefix=first.physical_prefix,
        physical_site_packages=second_site,
        logical_prefix=r"c:\VENV",
        logical_site_packages=r"c:\VENV\lib\ALTERNATE",
        path_flavor=PathFlavor.WINDOWS,
        case_rule=CaseRule.INSENSITIVE,
    )
    install_distribution(first, name="first")
    install_distribution(second, name="second")

    result = collect_distributions(layouts=(second, first))

    assert [distribution.name for distribution in result] == ["first", "second"]


def test_scan_is_direct_child_only_and_wraps_invalid_dist_info(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    nested = layout.physical_site_packages / "nested" / "Ignored-1.dist-info"
    nested.mkdir(parents=True)
    bad = layout.physical_site_packages / "opaque.dist-info"
    bad.mkdir()

    with pytest.raises(InventoryScanError) as error:
        collect_distributions(layouts=(layout,))

    assert error.value.code is InventoryScanErrorCode.INVALID_DIST_INFO
    assert error.value.target == "opaque.dist-info"


def test_scan_wraps_site_packages_filesystem_error(tmp_path, monkeypatch):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    original_iterdir = Path.iterdir

    def guarded_iterdir(path):
        if path == layout.physical_site_packages:
            raise PermissionError("denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    with pytest.raises(InventoryScanError) as error:
        collect_distributions(layouts=(layout,))

    assert error.value.code is InventoryScanErrorCode.FILESYSTEM_ERROR


def test_supplemental_adds_only_explicit_exact_file(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="example")
    scripts = layout.physical_prefix / "bin"
    scripts.mkdir()
    (scripts / "tool").write_bytes(b"tool")
    (scripts / "not-owned").write_bytes(b"sibling")
    ownership = SupplementalOwnership(
        distribution_name="Example",
        distribution_version="1",
        paths=("bin/tool", "bin/tool"),
    )

    result = collect_distributions(layouts=(layout,), supplemental=(ownership,))[0]

    discovered = [file for file in result.files if file.origin is FileOrigin.DISCOVERED]
    assert [file.path for file in discovered] == ["bin/tool"]
    assert all(file.path != "bin/not-owned" for file in result.files)


def test_supplemental_duplicate_case_aliases_are_order_independent(tmp_path):
    layout, original = windows_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="example")
    scripts = layout.physical_prefix / "Scripts"
    scripts.mkdir()
    (scripts / "Tool.EXE").write_bytes(b"tool")
    first = SupplementalOwnership(
        distribution_name="example",
        distribution_version="1",
        paths=("scripts/tool.exe", "scripts/tool.exe"),
    )
    second = SupplementalOwnership(
        distribution_name="example",
        distribution_version="1",
        paths=("Scripts/Tool.EXE",),
    )

    forward = collect_distributions(layouts=(layout,), supplemental=(first, second))
    reverse = collect_distributions(layouts=(layout,), supplemental=(second, first))

    assert forward == reverse
    discovered = [
        file for file in forward[0].files if file.origin is FileOrigin.DISCOVERED
    ]
    assert len(discovered) == 1
    assert discovered[0].canonical_identity == "scripts/tool.exe"


def test_supplemental_allows_compatible_shared_ownership(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="first")
    install_distribution(layout, name="second")
    shared = layout.physical_prefix / "bin" / "shared"
    shared.parent.mkdir()
    shared.write_bytes(b"shared")
    supplemental = tuple(
        SupplementalOwnership(
            distribution_name=name,
            distribution_version="1",
            paths=("bin/shared",),
        )
        for name in ("second", "first")
    )

    result = collect_distributions(layouts=(layout,), supplemental=supplemental)

    assert [distribution.name for distribution in result] == ["first", "second"]
    assert all(
        any(
            file.canonical_identity == "bin/shared"
            and file.origin is FileOrigin.DISCOVERED
            for file in distribution.files
        )
        for distribution in result
    )


def test_record_and_discovered_shared_ownership_builds_analysis_result(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    first_info, _first_file = install_distribution(layout, name="first")
    install_distribution(layout, name="second")
    shared = layout.physical_prefix / "bin" / "shared"
    shared.parent.mkdir()
    shared.write_bytes(b"shared")
    write_record(first_info, [("../../../bin/shared", "", "")])
    supplemental = SupplementalOwnership(
        distribution_name="second",
        distribution_version="1",
        paths=("bin/shared",),
    )

    distributions = collect_distributions(
        layouts=(layout,), supplemental=(supplemental,)
    )
    analysis = AnalysisResult(
        context=ResolutionContext(
            requirements=("first", "second"),
            python_version="3.12",
            platform="linux",
            architecture="x86_64",
            uv_version="test",
            build_policy=BuildPolicy.WHEEL_ONLY,
            compile_bytecode=True,
        ),
        distributions=distributions,
    )

    assert analysis.total_logical_bytes == sum(
        {
            file.canonical_identity: file.logical_bytes
            for distribution in distributions
            for file in distribution.files
        }.values()
    )
    assert analysis.duplicate_ownerships[0].canonical_identity == "bin/shared"


def test_resolve_supplemental_path_is_prefix_relative_and_case_aware(tmp_path):
    layout, _dist_info = windows_layout(tmp_path)
    resolved = resolve_supplemental_path(
        layout=layout,
        supplemental_path="Scripts/Tool.EXE",
    )

    assert resolved.path == "Scripts/Tool.EXE"
    assert resolved.canonical_identity == "scripts/tool.exe"
    assert resolved.physical_path == layout.physical_prefix / "Scripts" / "Tool.EXE"


def test_supplemental_preserves_higher_priority_record_claim(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    _dist_info, owned = install_distribution(layout, name="example")
    ownership = SupplementalOwnership(
        distribution_name="example",
        distribution_version="1",
        paths=(owned.relative_to(layout.physical_prefix).as_posix(),),
    )

    result = collect_distributions(layouts=(layout,), supplemental=(ownership,))[0]

    entry = next(file for file in result.files if file.path.endswith("/example.py"))
    assert entry.origin is FileOrigin.RECORD
    assert not any(file.origin is FileOrigin.DISCOVERED for file in result.files)


def test_supplemental_preserves_missing_record_claim(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    dist_info = layout.physical_site_packages / "Example-1.dist-info"
    dist_info.mkdir()
    write_metadata(dist_info, name="example")
    write_record(dist_info, [("missing.py", "", "")])
    path = "lib/python3.12/site-packages/missing.py"
    ownership = SupplementalOwnership(
        distribution_name="example", distribution_version="1", paths=(path,)
    )

    result = collect_distributions(layouts=(layout,), supplemental=(ownership,))[0]

    assert not any(file.origin is FileOrigin.DISCOVERED for file in result.files)
    assert WarningCode.MISSING_FILE in {warning.code for warning in result.warnings}


def test_supplemental_preserves_generated_and_fallback_claims(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    dist_info, source = install_distribution(layout, name="example")
    bytecode = source.parent / "__pycache__" / "example.cpython-312.pyc"
    bytecode.parent.mkdir()
    bytecode.write_bytes(b"bytecode")
    generated_path = bytecode.relative_to(layout.physical_prefix).as_posix()
    generated = SupplementalOwnership(
        distribution_name="example",
        distribution_version="1",
        paths=(generated_path,),
    )

    generated_result = collect_distributions(
        layouts=(layout,), supplemental=(generated,)
    )[0]
    (dist_info / "RECORD").unlink()
    fallback_path = (
        (dist_info / "METADATA").relative_to(layout.physical_prefix).as_posix()
    )
    fallback = SupplementalOwnership(
        distribution_name="example",
        distribution_version="1",
        paths=(fallback_path,),
    )
    fallback_result = collect_distributions(
        layouts=(layout,), supplemental=(fallback,)
    )[0]

    assert (
        next(
            file for file in generated_result.files if file.path == generated_path
        ).origin
        is FileOrigin.GENERATED
    )
    assert (
        next(
            file for file in fallback_result.files if file.path == fallback_path
        ).origin
        is FileOrigin.FALLBACK
    )


@pytest.mark.parametrize("path", ["/absolute", "C:/absolute", "a/../b", "a//b"])
def test_supplemental_rejects_noncanonical_paths_without_leaking_input(tmp_path, path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="example")
    ownership = SupplementalOwnership(
        distribution_name="example", distribution_version="1", paths=(path,)
    )

    with pytest.raises(SupplementalInventoryError) as error:
        collect_distributions(layouts=(layout,), supplemental=(ownership,))

    assert error.value.code is SupplementalErrorCode.INVALID_PATH
    assert error.value.target == "supplemental-path"
    assert path not in str(error.value)


def test_supplemental_reports_unknown_owner_and_missing_file(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="example")
    unknown = SupplementalOwnership(
        distribution_name="other", distribution_version="1", paths=("bin/tool",)
    )
    missing = SupplementalOwnership(
        distribution_name="example", distribution_version="1", paths=("bin/tool",)
    )

    with pytest.raises(SupplementalInventoryError) as unknown_error:
        collect_distributions(layouts=(layout,), supplemental=(unknown,))
    with pytest.raises(SupplementalInventoryError) as missing_error:
        collect_distributions(layouts=(layout,), supplemental=(missing,))

    assert unknown_error.value.code is SupplementalErrorCode.UNKNOWN_OWNER
    assert missing_error.value.code is SupplementalErrorCode.MISSING_FILE
    assert missing_error.value.target == "bin/tool"


def test_supplemental_constructor_rejects_empty_or_plain_string_paths():
    with pytest.raises(ValueError, match="non-empty"):
        SupplementalOwnership(
            distribution_name="example", distribution_version="1", paths=()
        )
    with pytest.raises(TypeError, match="tuple"):
        SupplementalOwnership(
            distribution_name="example",
            distribution_version="1",
            paths=cast(Any, "bin/tool"),
        )
    with pytest.raises(InventoryError, match="name or version"):
        SupplementalOwnership(
            distribution_name="example", distribution_version="", paths=("bin/tool",)
        )


def test_supplemental_rejects_directory_and_symlink_escape(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="example")
    (layout.physical_prefix / "data").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"secret")
    (layout.physical_prefix / "escape").symlink_to(outside, target_is_directory=True)

    for path, code in (
        ("data", SupplementalErrorCode.UNSUPPORTED_FILE_TYPE),
        ("escape/secret", SupplementalErrorCode.OUTSIDE_PREFIX),
    ):
        ownership = SupplementalOwnership(
            distribution_name="example", distribution_version="1", paths=(path,)
        )
        with pytest.raises(SupplementalInventoryError) as error:
            collect_distributions(layouts=(layout,), supplemental=(ownership,))
        assert error.value.code is code


def test_supplemental_accepts_final_symlink_without_following_target(tmp_path):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    install_distribution(layout, name="example")
    outside = tmp_path / "outside-secret"
    outside.write_bytes(b"secret target content")
    link = layout.physical_prefix / "bin" / "tool"
    link.parent.mkdir()
    link.symlink_to(outside)
    ownership = SupplementalOwnership(
        distribution_name="example",
        distribution_version="1",
        paths=("bin/tool",),
    )

    result = collect_distributions(layouts=(layout,), supplemental=(ownership,))[0]

    entry = next(file for file in result.files if file.path == "bin/tool")
    assert entry.origin is FileOrigin.DISCOVERED
    assert entry.logical_bytes == link.lstat().st_size
    assert entry.logical_bytes != outside.stat().st_size
    assert entry.symlink_target == os.readlink(link)


def test_scan_rejects_conflicting_shared_file_signatures(tmp_path, monkeypatch):
    layout, original = posix_layout(tmp_path)
    original.rmdir()
    first = layout.physical_site_packages / "First-1.dist-info"
    second = layout.physical_site_packages / "Second-1.dist-info"
    first.mkdir()
    second.mkdir()

    def fake_collect_distribution(*, layout, dist_info_dir):
        del layout
        size = 1 if dist_info_dir == first else 2
        return DistributionResult(
            name=dist_info_dir.name.split("-", 1)[0],
            version="1",
            files=(
                FileEntry(
                    path="shared",
                    canonical_identity="shared",
                    logical_bytes=size,
                    category=FileCategory.DATA,
                    origin=FileOrigin.RECORD,
                ),
            ),
        )

    monkeypatch.setattr(
        inventory_module, "collect_distribution", fake_collect_distribution
    )

    with pytest.raises(InventoryConflictError) as error:
        collect_distributions(layouts=(layout,))

    assert error.value.code is InventoryConflictErrorCode.FILE_SIGNATURE
    assert error.value.target == "shared"

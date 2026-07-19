import csv
import os
from pathlib import Path

import pytest

from uv_packsize.inventory import (
    CaseRule,
    InvalidRecordPathError,
    InventoryError,
    InventoryLayout,
    PathFlavor,
    RecordPathOutsidePrefixError,
    collect_distribution,
    resolve_record_path,
)
from uv_packsize.models import Completeness, FileCategory, FileOrigin, WarningCode


def write_metadata(
    dist_info: Path, name: str = "Example_Pkg", version: str = "1"
) -> None:
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )


def write_record(dist_info: Path, rows: list[tuple[str, str, str]]) -> None:
    with (dist_info / "RECORD").open("w", encoding="utf-8", newline="") as record:
        csv.writer(record).writerows(rows)


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
        path.stat().st_size for path in (source, bytecode, script, header)
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

    assert result.files == ()
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

    assert [entry.path for entry in result.files] == [
        "lib/python3.12/site-packages/data,part.csv"
    ]
    assert result.files[0].category is FileCategory.DATA


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

    assert len(result.files) == 1
    entry = result.files[0]
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

    assert result.files == ()
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

    assert len(result.files) == 3
    assert result.total_logical_bytes == len(b"content") * 2


def test_windows_case_collision_is_one_file_with_duplicate_warning(tmp_path):
    layout, dist_info = windows_layout(tmp_path)
    write_metadata(dist_info)
    file = layout.physical_site_packages / "Example.py"
    file.write_bytes(b"content")
    write_record(dist_info, [("Example.py", "", ""), ("example.PY", "", "")])

    result = collect_distribution(layout=layout, dist_info_dir=dist_info)

    assert len(result.files) == 1
    assert result.files[0].canonical_identity == "lib/site-packages/example.py"
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

    assert result.files[0].symlink_target == target


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

    assert result.files == ()
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

    assert result.files == ()
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

    assert len(result.files) == 1
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

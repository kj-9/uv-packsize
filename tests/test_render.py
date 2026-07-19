from typing import Any

import pytest

from uv_packsize.models import (
    AnalysisResult,
    AnalysisWarning,
    BuildPolicy,
    CaseRule,
    DistributionResult,
    FileCategory,
    FileEntry,
    FileOrigin,
    PathFlavor,
    ResolutionContext,
    WarningCode,
    WarningTargetKind,
)
from uv_packsize.render import format_size, render_analysis_report


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


def file_entry(
    path: str,
    size: int,
    *,
    category: FileCategory = FileCategory.PYTHON,
    identity: str | None = None,
) -> FileEntry:
    return FileEntry(
        path=path,
        canonical_identity=identity or path,
        logical_bytes=size,
        category=category,
        origin=FileOrigin.RECORD,
    )


def distribution(name: str, *files: FileEntry, warnings=()) -> DistributionResult:
    return DistributionResult(name=name, version="1", files=files, warnings=warnings)


@pytest.mark.parametrize(
    ("logical_bytes", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.00 KiB"),
        (1024**2, "1.00 MiB"),
        (1024**3, "1.00 GiB"),
    ],
)
def test_format_size_uses_binary_unit_boundaries(logical_bytes, expected):
    assert format_size(logical_bytes) == expected


@pytest.mark.parametrize(
    ("logical_bytes", "error", "message"),
    [
        (True, TypeError, "must be an int"),
        (1.5, TypeError, "must be an int"),
        (-1, ValueError, "must be non-negative"),
    ],
)
def test_format_size_rejects_invalid_values(logical_bytes, error, message):
    with pytest.raises(error, match=message):
        format_size(logical_bytes)


def test_renderer_orders_equal_distribution_sizes_by_name():
    result = AnalysisResult(
        context=context(),
        distributions=(
            distribution("zeta", file_entry("zeta.py", 10)),
            distribution("alpha", file_entry("alpha.py", 10)),
            distribution("middle", file_entry("middle.py", 5)),
        ),
    )

    report = render_analysis_report(result)

    assert report.index("alpha") < report.index("zeta") < report.index("middle")
    assert report.endswith("Total size:  25 B")


def test_renderer_explains_global_dedupe_without_exposing_owned_paths():
    result = AnalysisResult(
        context=context(),
        distributions=(
            distribution(
                "first",
                file_entry("private/first.py", 10),
                file_entry("private/shared.py", 40),
            ),
            distribution("second", file_entry("private/shared.py", 40)),
        ),
    )

    report = render_analysis_report(result)

    assert "Total Package Size  50 B" in report
    assert "Total size:  50 B" in report
    assert "distribution rows total 90 B" in report
    assert "duplicate-owned files are counted once globally" in report
    assert "private/shared.py" not in report


def test_renderer_summarizes_incomplete_warnings_without_targets():
    missing_file = AnalysisWarning(
        code=WarningCode.MISSING_FILE,
        target_kind=WarningTargetKind.FILE,
        target_identity="unsafe/path.txt",
    )
    missing_record = AnalysisWarning(
        code=WarningCode.MISSING_RECORD,
        target_kind=WarningTargetKind.DISTRIBUTION,
        target_identity="example==1",
    )
    result = AnalysisResult(
        context=context(),
        distributions=(
            distribution(
                "example",
                file_entry("example.py", 1),
                warnings=(missing_record,),
            ),
        ),
        warnings=(missing_file,),
    )

    report = render_analysis_report(result)

    assert (
        "Warning: incomplete analysis (missing-file: 1; missing-record: 1)." in report
    )
    assert "unsafe/path.txt" not in report
    assert "example==1" not in report


def test_renderer_splits_scripts_into_deduplicated_prefix_relative_binary_rows():
    shared_script = file_entry(
        "bin/shared-tool",
        4,
        category=FileCategory.SCRIPT,
    )
    result = AnalysisResult(
        context=context(),
        distributions=(
            distribution(
                "first",
                file_entry("first.py", 7),
                file_entry("shared.py", 3),
                file_entry("bin/first/tool", 5, category=FileCategory.SCRIPT),
                shared_script,
            ),
            distribution(
                "second",
                file_entry("shared.py", 3),
                file_entry("bin/second/tool", 6, category=FileCategory.SCRIPT),
                shared_script,
            ),
        ),
    )

    report = render_analysis_report(result, show_scripts=True)

    package_section, binary_section, *_rest = report.split("\n\n")
    assert "first" in package_section
    assert "second" in package_section
    assert package_section.splitlines()[-1].startswith("Total Package Size")
    assert package_section.splitlines()[-1].endswith("10 B")
    assert "Binaries in .venv/bin" in binary_section
    assert "bin/first/tool" in binary_section
    assert "bin/second/tool" in binary_section
    assert binary_section.count("bin/shared-tool") == 1
    assert "Total Binaries Size  15 B" in binary_section
    assert "displayed rows total 28 B" in report
    assert "Total size:  25 B" in report


def test_renderer_uses_a_deterministic_display_path_for_shared_windows_script():
    def analysis(first_path: str, second_path: str) -> AnalysisResult:
        return AnalysisResult(
            context=context(
                path_flavor=PathFlavor.WINDOWS,
                case_rule=CaseRule.INSENSITIVE,
            ),
            distributions=(
                distribution(
                    "alpha",
                    file_entry(
                        first_path,
                        4,
                        category=FileCategory.SCRIPT,
                        identity="scripts/tool.exe",
                    ),
                ),
                distribution(
                    "zeta",
                    file_entry(
                        second_path,
                        4,
                        category=FileCategory.SCRIPT,
                        identity="scripts/tool.exe",
                    ),
                ),
            ),
        )

    forward = render_analysis_report(
        analysis("Scripts/tool.exe", "Scripts/Tool.EXE"),
        show_scripts=True,
    )
    reverse = render_analysis_report(
        analysis("Scripts/Tool.EXE", "Scripts/tool.exe"),
        show_scripts=True,
    )

    assert forward == reverse
    assert forward.count("Scripts/Tool.EXE") == 1
    assert "scripts/tool.exe" not in forward


def test_renderer_renders_an_empty_analysis_cleanly():
    report = render_analysis_report(AnalysisResult(context=context(), distributions=()))

    assert report == (
        "--- Package Sizes ---\n"
        "No items to display.\n"
        "Total Package Size  0 B\n\n"
        "Total size:  0 B"
    )

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from uv_packsize.baseline import (
    BaselineDistribution,
    BaselineDuplicateOwnershipSummary,
    BaselineWarningSummary,
    parse_baseline_json,
)
from uv_packsize.diff import MAX_BASELINE_INTEGER, compare_baselines
from uv_packsize.diff_render import (
    _render_table,
    _safe_text,
    format_signed_size,
    render_diff_report,
    render_diff_sections,
)

ROOT = Path(__file__).parents[1]


def baseline():
    return parse_baseline_json(
        (ROOT / "tests" / "golden" / "analysis-result-v1.json").read_text()
    )


def compared(*, global_bytes: int | None = None, distributions=None, warnings=None):
    before = baseline()
    current = replace(
        before,
        global_logical_bytes=(
            before.global_logical_bytes if global_bytes is None else global_bytes
        ),
        distributions=before.distributions if distributions is None else distributions,
        warnings=before.warnings if warnings is None else warnings,
    )
    return compare_baselines(before, current)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 B"),
        (1, "+1 B"),
        (-1, "-1 B"),
        (1023, "+1023 B"),
        (1024, "+1.00 KiB"),
        (1024**2, "+1.00 MiB"),
        (1024**3, "+1.00 GiB"),
        (MAX_BASELINE_INTEGER, "+8589934592.00 GiB"),
    ],
)
def test_format_signed_size(value, expected):
    assert format_signed_size(value) == expected


@pytest.mark.parametrize("value", [True, False, None, "1"])
def test_format_signed_size_rejects_non_integers(value):
    with pytest.raises(TypeError, match="delta must be an int"):
        format_signed_size(value)


@pytest.mark.parametrize("value", [MAX_BASELINE_INTEGER + 1, -MAX_BASELINE_INTEGER - 1])
def test_format_signed_size_rejects_out_of_range_values(value):
    with pytest.raises(ValueError, match="signed diff range"):
        format_signed_size(value)


def test_empty_diff_has_canonical_global_section_and_no_distribution_changes():
    report = render_diff_report(compared())

    assert report.startswith("--- Size Comparison ---\nMetric")
    assert "Global logical size" in report
    assert "Distribution-owned aggregate" in report
    assert "--- Distribution Changes ---\nNo distribution changes." in report
    assert not report.endswith("\n")


def test_added_removed_and_changed_rows_are_canonical_and_distinguish_change_kinds():
    before = baseline()
    alpha, zeta = before.distributions
    current = replace(
        before,
        global_logical_bytes=80,
        distributions=(
            BaselineDistribution(name="aardvark", version="1", logical_bytes=3),
            replace(alpha, logical_bytes=alpha.logical_bytes + 5),
            replace(zeta, version="3", logical_bytes=zeta.logical_bytes + 7),
        ),
    )
    report = render_diff_report(compare_baselines(before, current))

    assert "--- Added Distributions ---" in report
    assert "aardvark" in report
    assert "--- Changed Distributions ---" in report
    assert "alpha-pkg" in report  # size-only, kind remains UNCHANGED
    assert "zeta" in report  # version and size changed
    assert "Change type" in report
    assert "alpha-pkg  1.0" in report
    assert "size" in report
    assert "version+size" in report
    assert "--- Removed Distributions ---" not in report
    assert report.index("alpha-pkg") < report.index("zeta")


def test_removed_and_version_only_rows_are_rendered():
    before = baseline()
    alpha, zeta = before.distributions
    current = replace(
        before,
        distributions=(replace(zeta, version="updated"),),
    )
    report = render_diff_report(compare_baselines(before, current))

    assert "--- Removed Distributions ---" in report
    assert alpha.name in report
    assert "--- Changed Distributions ---" in report
    assert "updated" in report
    assert "version" in report
    assert "0 B" in report


def test_changed_rows_use_exact_display_change_types():
    before = baseline()
    alpha, zeta = before.distributions
    beta = BaselineDistribution(name="beta", version="1", logical_bytes=10)
    before = replace(
        before,
        distributions=(
            alpha,
            beta,
            zeta,
        ),
    )
    current = replace(
        before,
        distributions=(
            replace(alpha, logical_bytes=alpha.logical_bytes + 1),
            replace(beta, version="2"),
            replace(zeta, version="both", logical_bytes=zeta.logical_bytes + 1),
        ),
    )
    changed_lines = render_diff_report(compare_baselines(before, current)).splitlines()
    types = {
        line.split()[0]: line.split()[-3]
        for line in changed_lines
        if line.startswith(("alpha-pkg", "beta", "zeta"))
    }

    assert types == {"alpha-pkg": "size", "beta": "version", "zeta": "version+size"}


def test_nonreconciliation_note_only_appears_when_aggregate_and_global_delta_differ():
    before = baseline()
    changed = compared(global_bytes=before.global_logical_bytes + 1)
    report = render_diff_report(changed)

    assert "does not reconcile" in report
    assert "duplicate-owned files" in report
    assert "+1 B" in report
    assert "does not reconcile" not in render_diff_report(compared())


def test_incomplete_warning_is_safe_and_uses_baseline_then_current_code_counts():
    before = baseline()
    secret = "target\\nwith-control"
    incomplete = replace(
        before,
        warnings=BaselineWarningSummary(
            completeness="incomplete",
            warning_code_counts=(
                ("duplicate-ownership", 1),
                ("missing-file", 2),
            ),
        ),
    )
    # The renderer receives only summaries; this secret asserts no baseline repr leaks.
    report = render_diff_report(compare_baselines(before, incomplete))

    assert "baseline: duplicate-ownership: 1, missing-file: 1" in report
    assert "current: duplicate-ownership: 1, missing-file: 2" in report
    assert report.index("baseline:") < report.index("current:")
    assert "deltas may be partial" in report
    assert secret not in report
    assert "fingerprint" not in report


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("full\u3000width", "full\\u3000width"),
        ("combininge\u0301", "combininge\\u0301"),
        ("emoji\U0001f642", "emoji\\U0001F642"),
        ("bidi\u202e", "bidi?"),
        ("control\x1b[31m\n", "control?[31m?"),
    ],
)
def test_safe_text_uses_ascii_escape_or_control_replacement(value, expected):
    assert _safe_text(value) == expected
    assert _safe_text(value).isascii()


def test_terminal_controls_and_wide_versions_are_safe_and_table_aligned():
    before = baseline()
    alpha, zeta = before.distributions
    current = replace(
        before,
        distributions=(
            replace(alpha, version="new\x1b[31m\n\U0001f642"),
            zeta,
        ),
    )
    report = render_diff_report(compare_baselines(before, current))

    assert "new?[31m?\\U0001F642" in report
    assert "\\x1b" not in report
    assert "\nnew" not in report


def test_table_alignment_is_exact_for_ascii_normalized_values():
    lines = _render_table(
        ("Name", "Version", "Change"),
        (("alpha", _safe_text("wide\u3000"), "+1 B"), ("beta", "1", "+1.00 MiB")),
        (2,),
    )

    assert lines[2].index("+1 B") + len("+1 B") == lines[3].index("+1.00 MiB") + len(
        "+1.00 MiB"
    )


def test_zero_distribution_baseline_renders_zero_global_and_aggregate_rows():
    source = baseline()
    empty = replace(
        source,
        global_logical_bytes=0,
        distributions=(),
        warnings=BaselineWarningSummary(
            completeness="complete", warning_code_counts=()
        ),
        duplicate_ownership=BaselineDuplicateOwnershipSummary(present=False, count=0),
    )
    report = render_diff_report(compare_baselines(empty, empty))

    assert report.count("0 B") >= 6
    assert "No distribution changes." in report


def test_private_context_and_baseline_repr_are_not_rendered():
    source = baseline()
    private_fingerprint = "a" * 64
    context = replace(
        source.resolution_context, platform_fingerprint=private_fingerprint
    )
    private_version = "private\x1b\u3000"
    baseline_with_private_context = replace(source, resolution_context=context)
    alpha, zeta = baseline_with_private_context.distributions
    current = replace(
        baseline_with_private_context,
        distributions=(replace(alpha, version=private_version), zeta),
    )
    report = render_diff_report(
        compare_baselines(baseline_with_private_context, current)
    )

    assert private_fingerprint not in report
    assert "Baseline(" not in report
    assert "private?\\u3000" in report


@pytest.mark.parametrize("value", [None, object(), baseline()])
def test_renderers_reject_wrong_diff_type(value: Any):
    with pytest.raises(TypeError, match="AnalysisDiff"):
        render_diff_report(value)
    with pytest.raises(TypeError, match="AnalysisDiff"):
        render_diff_sections(value)


def test_report_and_sections_are_equivalent():
    diff = compared()
    assert render_diff_report(diff) == "\n\n".join(render_diff_sections(diff))
